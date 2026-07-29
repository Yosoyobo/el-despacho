"""Mini-Chalán de tareas del proyecto (LC 2026-07-29).

Oscar: «junto al botón +Nueva tarea agreguemos un botón para poder describir y
sumar tareas con el Chalán. Lo menos invasivo y que no nos saque de la página».

El usuario dicta en lenguaje natural («el lunes Karla manda el arte y el jueves
recogemos las gorras en Tizayuca») y El Chalán lo convierte a tareas concretas.
Lo que importa es **qué / quién / cuándo** — el resto son defaults.

**Propone, no aplica** (regla §20): la vista muestra un preview con checkboxes y
el usuario confirma cuáles crear. Diseño defensivo, espejo de `productos_ia`:
`interpretar_tareas` NUNCA lanza — devuelve `{ok, tareas, error}`;
`aplicar_tareas` re-valida el permiso antes de tocar la base.
"""

from __future__ import annotations

import json
import re
from datetime import date

_MAX_TOKENS = 900
_MAX_TAREAS = 25

_TIPOS = {"tarea", "entrega", "junta", "recoger"}
_PRIORIDADES = {"baja", "media", "alta"}


def _parsear_json(texto: str) -> dict | None:
    if not texto:
        return None
    limpio = re.sub(r"^```(?:json)?", "", texto.strip()).strip()
    limpio = re.sub(r"```$", "", limpio).strip()
    m = re.search(r"\{.*\}", limpio, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _fecha(valor, default: date) -> date:
    """Fecha ISO del LLM → `date`. Cualquier basura cae al default."""
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor.strip()[:10])
        except ValueError:
            pass
    return default


def _personas(proyecto):
    """Candidatos a responsable: el equipo del proyecto primero, luego el resto.

    Se limita a activos. El equipo va primero para que el LLM prefiera a quien ya
    trabaja el proyecto cuando el usuario dice sólo un nombre de pila.
    """
    from cuentas.models.usuario import Usuario

    del_equipo = list(
        Usuario.objects.filter(is_active=True, asignaciones_proyecto__proyecto=proyecto)
        .order_by("nombre_completo").distinct()
    )
    ids = {u.pk for u in del_equipo}
    resto = [
        u for u in Usuario.objects.filter(is_active=True).order_by("nombre_completo")[:80]
        if u.pk not in ids
    ]
    return del_equipo, resto


def _resolver_persona(nombre: str, candidatos: list):
    """Usuario por nombre: exacto → empieza-con → contiene, y sólo si es
    inequívoco (dos «Karla» no se adivinan). None si no se pudo resolver."""
    n = (nombre or "").strip().lower()
    if not n:
        return None

    def _unico(coincidencias):
        return coincidencias[0] if len(coincidencias) == 1 else None

    nombres = [((u.nombre_completo or u.email or "").strip().lower(), u) for u in candidatos]
    if (u := _unico([u for txt, u in nombres if txt == n])):
        return u
    if (u := _unico([u for txt, u in nombres if txt.startswith(n)])):
        return u
    if (u := _unico([u for txt, u in nombres if n in txt])):
        return u
    # Nombre de pila: casa contra la primera palabra de cada nombre completo.
    return _unico([u for txt, u in nombres if txt.split(" ")[0] == n])


def interpretar_tareas(*, proyecto, texto: str, usuario) -> dict:
    """Interpreta `texto` a tareas del `proyecto`. Nunca lanza."""
    texto = (texto or "").strip()
    if not texto:
        return {"ok": False, "error": "Describe primero las tareas.", "tareas": []}

    del_equipo, resto = _personas(proyecto)
    candidatos = del_equipo + resto
    lista_equipo = "\n".join(f"- {u.nombre_completo or u.email}" for u in del_equipo)
    lista_resto = "\n".join(f"- {u.nombre_completo or u.email}" for u in resto)
    hoy = date.today()

    system = (
        "Eres El Chalán de Learning Center, un despacho mexicano de diseño y maquila. "
        "El usuario dicta las tareas de un proyecto y tú las conviertes a tareas "
        "concretas. Lo esencial es QUÉ, QUIÉN y CUÁNDO. Responde SOLO JSON estricto, "
        "sin texto fuera:\n"
        '{"tareas": [{"titulo": "<qué hay que hacer, imperativo y corto>", '
        '"responsable": "<nombre tal como está en la lista, o vacío>", '
        '"fecha": "YYYY-MM-DD", "tipo": "tarea|entrega|junta|recoger", '
        '"prioridad": "baja|media|alta", "detalle": "<texto corto|vacío>"}]}\n'
        "Reglas: una tarea por cada cosa que haya que hacer; no inventes tareas que "
        "el usuario no pidió. Usa el NOMBRE EXACTO de la lista de personas; si no "
        "queda claro quién, deja `responsable` vacío. Resuelve las fechas relativas "
        "(«mañana», «el lunes», «en dos semanas») a fecha ISO contra la fecha de hoy "
        "que te doy; si no se menciona fecha, usa la de hoy. `tipo`: 'entrega' si se "
        "entrega algo al cliente, 'recoger' si hay que ir a recoger o pasar por algo, "
        "'junta' si es una reunión, 'tarea' en cualquier otro caso. `prioridad` "
        "'media' salvo que el usuario marque urgencia."
    )
    user = (
        f"HOY es {hoy:%Y-%m-%d} ({hoy:%A}).\n"
        f"PROYECTO: {proyecto.nombre or proyecto.codigo}\n\n"
        f"EQUIPO DEL PROYECTO (prefiere a estas personas):\n{lista_equipo or '(sin equipo asignado)'}\n\n"
        f"OTRAS PERSONAS DEL TALLER:\n{lista_resto or '(ninguna)'}\n\n"
        f"DICTADO DEL USUARIO:\n{texto}"
    )

    try:
        from chalanes.voz import preludio, reglas
        from lib.analistas import PresupuestoIAExcedido, analizar
        from lib.sanear import sanear_contexto
        prompt = preludio("dictado") + system + reglas() + "\n\n" + sanear_contexto(user, max_len=5000)
        try:
            res = analizar(estacion="dictado", prompt=prompt, max_tokens=_MAX_TOKENS,
                           temperatura=0.1, actor_id=getattr(usuario, "pk", None))
        except PresupuestoIAExcedido:
            return {"ok": False, "tareas": [],
                    "error": "Se alcanzó el tope de gasto de IA del mes. Crea las tareas a mano."}
    except Exception as exc:  # noqa: BLE001 — nunca tumbar el flujo
        return {"ok": False, "tareas": [], "error": f"El Chalán no respondió: {str(exc)[:200]}"}

    crudo = _parsear_json(getattr(res, "texto", "") or "")
    if not crudo or not isinstance(crudo.get("tareas"), list):
        return {"ok": False, "tareas": [],
                "error": "El Chalán no devolvió tareas legibles. Intenta describirlas de otra forma."}

    tareas = []
    for item in crudo["tareas"][:_MAX_TAREAS]:
        if not isinstance(item, dict):
            continue
        titulo = (item.get("titulo") or "").strip()[:200]
        if not titulo:
            continue
        persona = _resolver_persona(item.get("responsable") or "", candidatos)
        tipo = (item.get("tipo") or "tarea").strip().lower()
        prioridad = (item.get("prioridad") or "media").strip().lower()
        tareas.append({
            "titulo": titulo,
            "asignada_id": persona.pk if persona else None,
            "asignada_nombre": (persona.nombre_completo or persona.email) if persona else "",
            "fecha": _fecha(item.get("fecha"), hoy).isoformat(),
            "tipo": tipo if tipo in _TIPOS else "tarea",
            "prioridad": prioridad if prioridad in _PRIORIDADES else "media",
            "detalle": (item.get("detalle") or "").strip()[:500],
        })

    if not tareas:
        return {"ok": False, "tareas": [],
                "error": "El Chalán no identificó tareas en la descripción."}
    return {"ok": True, "tareas": tareas, "error": ""}


def aplicar_tareas(*, proyecto, tareas: list[dict], usuario) -> dict:
    """Crea las `Tarea` seleccionadas. Re-valida permisos (defensa en profundidad).

    Una tarea sin responsable resuelto se asigna a quien la está creando: el
    modelo lo permite vacío, pero una tarea sin dueño no le sirve a nadie.
    """
    from apps.el_pizarron.models import Tarea

    from cuentas.models.usuario import Usuario
    from lib.permisos import puede_editar_proyecto

    if not puede_editar_proyecto(usuario, proyecto):
        return {"creadas": 0, "omitidas": 0, "mensajes": ["Sin permiso para editar el proyecto."]}

    creadas, omitidas, mensajes = 0, 0, []
    hoy = date.today()
    for t in tareas:
        titulo = (t.get("titulo") or "").strip()[:200]
        if not titulo:
            omitidas += 1
            continue
        asignada = None
        if (aid := t.get("asignada_id")):
            asignada = Usuario.objects.filter(pk=aid, is_active=True).first()
        if asignada is None:
            asignada = usuario
        tipo = (t.get("tipo") or "tarea").strip().lower()
        prioridad = (t.get("prioridad") or "media").strip().lower()
        tarea = Tarea.objects.create(
            proyecto=proyecto,
            titulo=titulo,
            descripcion=(t.get("detalle") or "").strip()[:500],
            tipo=tipo if tipo in _TIPOS else "tarea",
            prioridad=prioridad if prioridad in _PRIORIDADES else "media",
            asignada_a=asignada,
            fecha_compromiso=_fecha(t.get("fecha"), hoy),
            creado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        )
        _notificar(tarea, proyecto, usuario)
        creadas += 1

    if omitidas:
        mensajes.append(f"{omitidas} tarea(s) sin título se omitieron.")
    return {"creadas": creadas, "omitidas": omitidas, "mensajes": mensajes}


def _notificar(tarea, proyecto, usuario) -> None:
    """Evento + push + actividad, igual que el alta manual. Best-effort."""
    import contextlib
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="tarea.creada",
            actor_id=getattr(usuario, "pk", None), actor_email=getattr(usuario, "email", None),
            payload={"tarea_id": tarea.pk, "proyecto_id": proyecto.pk, "origen": "chalan_proyecto"},
        ))
    with contextlib.suppress(Exception):
        from apps.taller_home.push_handlers import notificar_tarea_asignada
        notificar_tarea_asignada(tarea, usuario)
    with contextlib.suppress(Exception):
        from . import servicios_actividad
        servicios_actividad.registrar(
            proyecto=proyecto, tipo="tarea_creada",
            descripcion=f"Nueva tarea «{tarea.titulo[:60]}» (dictada al Chalán)",
            actor=usuario, url=f"/proyectos/{proyecto.pk}/",
        )


__all__ = ["interpretar_tareas", "aplicar_tareas"]
