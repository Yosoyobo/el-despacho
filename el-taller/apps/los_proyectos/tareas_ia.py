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

LC 2026-08-28 (Oscar, nota 6): además de qué/quién/cuándo, ahora entiende la
HORA y el LUGAR («entregar el martes a las 4 en la bodega de Optimist»), y la
tarea puede quedar LIGADA a una línea de producto del proyecto — así la tarjeta
lista «las tareas de este producto».

**Las coordenadas no se inventan** (ver `_resolver_lugar`): el pin sólo se pone
cuando el lugar dicho empata con una dirección YA GUARDADA (una sede de LC, o
dónde se ha visitado al cliente o a un proveedor del proyecto). Si no empata, se
guarda sólo la etiqueta: el runner la lee igual y el pin se fija después desde el
mapa del mandado. Un pin inventado manda a alguien al lugar equivocado, que es
mucho peor que no tener pin.
"""

from __future__ import annotations

import json
import re
from datetime import date, time

_MAX_TOKENS = 900
_MAX_TAREAS = 25
# Un nombre corto («sur», «casa») aparece por casualidad dentro de cualquier
# frase y pondría el pin en otro lado. Con nombres cortos, mejor sin pin.
_MIN_NOMBRE_LUGAR = 5

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


def _hora(valor) -> str:
    """«16:30» del LLM → "HH:MM". Cualquier otra cosa → "" (la tarea queda sin
    hora, que es lo correcto: nadie dijo a qué hora)."""
    if not isinstance(valor, str):
        return ""
    m = re.match(r"^\s*(\d{1,2})[:.](\d{2})", valor.strip())
    if not m:
        return ""
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return ""
    return f"{h:02d}:{mi:02d}"


def _hora_obj(valor):
    """La misma hora de `_hora`, ya como `datetime.time` (o None).

    Se convierte aquí y no al guardar: Django aceptaría la cadena, pero la
    instancia en memoria se quedaría con texto y quien la lea justo después
    (los avisos, el mandado) compararía manzanas con peras.
    """
    txt = _hora(valor)
    if not txt:
        return None
    h, mi = txt.split(":")
    return time(int(h), int(mi))


def _lugares_conocidos(proyecto) -> list[tuple[str, float, float]]:
    """Direcciones YA GUARDADAS contra las que se puede empatar un lugar dicho.

    Tres fuentes, todas del propio sistema: las sedes de LC con pin, dónde se ha
    visitado al cliente del proyecto, y dónde se ha visitado a cada proveedor de
    sus líneas. Devuelve `(nombre, lat, lng)`.

    Nunca lanza: si algo falla (una app que no está, la base sin migrar) se
    queda sin candidatos y la tarea guarda sólo la etiqueta.
    """
    import contextlib
    fuentes: list[tuple[str, float, float]] = []

    with contextlib.suppress(Exception):
        from apps.checador.models.sede import SedeLC
        for s in SedeLC.objects.filter(activa=True, lat__isnull=False, lng__isnull=False):
            fuentes.append((s.nombre, float(s.lat), float(s.lng)))

    with contextlib.suppress(Exception):
        from apps.checador import services as checador
        if proyecto.cliente_id:
            v = checador.ultima_ubicacion_de(cliente=proyecto.cliente)
            if v is not None:
                fuentes.append((proyecto.cliente.razon_social, float(v.lat), float(v.lng)))
        vistos = set()
        for pp in proyecto.productos.select_related("proveedor").all():
            prov = pp.proveedor
            if prov is None or prov.pk in vistos:
                continue
            vistos.add(prov.pk)
            v = checador.ultima_ubicacion_de(proveedor=prov)
            if v is not None:
                fuentes.append((prov.razon_social, float(v.lat), float(v.lng)))

    return fuentes


def _resolver_lugar(lugar: str, proyecto) -> tuple[float | None, float | None]:
    """Pin del lugar dicho, SÓLO si empata con una dirección ya guardada.

    Empata cuando el nombre conocido aparece dentro de lo que dictó el usuario
    («la bodega de Optimist» → el cliente «Optimist»), o al revés. Se exige que
    la coincidencia sea INEQUÍVOCA: dos candidatos distintos ⇒ ningún pin. Un
    pin inventado manda a alguien al lugar equivocado; una etiqueta sin pin sólo
    obliga a picarlo después en el mapa.
    """
    from lib.nombres import normalizar
    aguja = normalizar(lugar)
    if not aguja:
        return (None, None)
    encontrados: list[tuple[float, float]] = []
    for nombre, lat, lng in _lugares_conocidos(proyecto):
        n = normalizar(nombre)
        if len(n) < _MIN_NOMBRE_LUGAR:
            continue
        if n in aguja or aguja in n:
            punto = (lat, lng)
            if punto not in encontrados:
                encontrados.append(punto)
    return encontrados[0] if len(encontrados) == 1 else (None, None)


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


def interpretar_tareas(*, proyecto, texto: str, usuario, producto=None) -> dict:
    """Interpreta `texto` a tareas del `proyecto`. Nunca lanza.

    `producto` es la línea del proyecto desde cuya tarjeta se dictó, si se dictó
    desde una. Sólo entra al prompt como contexto (el vínculo lo pone
    `aplicar_tareas`), para que el Chalán sepa de qué producto se está hablando
    y no haya que repetirlo en el dictado.
    """
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
        '"fecha": "YYYY-MM-DD", "hora": "HH:MM o vacío", '
        '"lugar": "<dónde, tal como lo dijo el usuario, o vacío>", '
        '"tipo": "tarea|entrega|junta|recoger", '
        '"prioridad": "baja|media|alta", "detalle": "<texto corto|vacío>"}]}\n'
        "Reglas: una tarea por cada cosa que haya que hacer; no inventes tareas que "
        "el usuario no pidió. Usa el NOMBRE EXACTO de la lista de personas SOLO si "
        "el usuario dijo a quién; si no lo dijo, deja `responsable` VACÍO — nunca "
        "adivines ni la asignes a quien está dictando. Resuelve las fechas relativas "
        "(«mañana», «el lunes», «en dos semanas») a fecha ISO contra la fecha de hoy "
        "que te doy; si no se menciona fecha, usa la de hoy. `tipo`: 'entrega' si se "
        "entrega algo al cliente, 'recoger' si hay que ir a recoger o pasar por algo, "
        "'junta' si es una reunión, 'tarea' en cualquier otro caso. `prioridad` "
        "'media' salvo que el usuario marque urgencia. `hora` en 24 horas SÓLO si "
        "el usuario dijo una («a las 4 de la tarde» → 16:00); si no la dijo, "
        "déjala VACÍA — no inventes horarios. `lugar`: dónde hay que ir o entregar, "
        "tal como lo dijo el usuario («la bodega de Optimist»); vacío si no dijo "
        "lugar. No inventes direcciones ni coordenadas: sólo repites lo que dijo."
    )
    ctx_producto = ""
    if producto is not None:
        ctx_producto = (
            f"PRODUCTO DE ESTE PROYECTO del que se está hablando: "
            f"{producto.nombre_visible}"
            f"{f' ({producto.cantidad} pz)' if producto.cantidad else ''}\n"
            "Las tareas que se dicten son de ESE producto.\n\n"
        )
    user = (
        f"HOY es {hoy:%Y-%m-%d} ({hoy:%A}).\n"
        f"PROYECTO: {proyecto.nombre or proyecto.codigo}\n\n"
        f"{ctx_producto}"
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
        lugar = (item.get("lugar") or "").strip()[:200]
        lat, lng = _resolver_lugar(lugar, proyecto) if lugar else (None, None)
        tareas.append({
            "titulo": titulo,
            "asignada_id": persona.pk if persona else None,
            "asignada_nombre": (persona.nombre_completo or persona.email) if persona else "",
            "fecha": _fecha(item.get("fecha"), hoy).isoformat(),
            "hora": _hora(item.get("hora")),
            "lugar": lugar,
            # El pin sólo viaja si el lugar empató con una dirección guardada.
            "lat": lat,
            "lng": lng,
            "tipo": tipo if tipo in _TIPOS else "tarea",
            "prioridad": prioridad if prioridad in _PRIORIDADES else "media",
            "detalle": (item.get("detalle") or "").strip()[:500],
        })

    if not tareas:
        return {"ok": False, "tareas": [],
                "error": "El Chalán no identificó tareas en la descripción."}
    return {"ok": True, "tareas": tareas, "error": ""}


def aplicar_tareas(*, proyecto, tareas: list[dict], usuario, producto=None) -> dict:
    """Crea las `Tarea` seleccionadas. Re-valida permisos (defensa en profundidad).

    Una tarea sin responsable resuelto se queda SIN responsable, general del
    despacho (Oscar, LC 2026-08-07: «no debe de asignar a nadie si no se lo
    digo»). Antes caía a quien la dictaba, y terminaba con tareas ajenas
    colgadas de su nombre.

    `producto` (LC 2026-08-28): la línea del proyecto desde cuya tarjeta se
    dictó. Queda ligada a cada tarea creada. Se ignora si la línea es de otro
    proyecto — una tarea no puede colgar de un producto ajeno.
    """
    from apps.el_pizarron.models import Tarea

    from cuentas.models.usuario import Usuario
    from lib.permisos import puede_editar_proyecto

    if not puede_editar_proyecto(usuario, proyecto):
        return {"creadas": 0, "omitidas": 0, "mensajes": ["Sin permiso para editar el proyecto."]}

    creadas, omitidas, mensajes = 0, 0, []
    hoy = date.today()
    if producto is not None and producto.proyecto_id != proyecto.pk:
        producto = None
    for t in tareas:
        titulo = (t.get("titulo") or "").strip()[:200]
        if not titulo:
            omitidas += 1
            continue
        asignada = None
        if (aid := t.get("asignada_id")):
            asignada = Usuario.objects.filter(pk=aid, is_active=True).first()
        tipo = (t.get("tipo") or "tarea").strip().lower()
        prioridad = (t.get("prioridad") or "media").strip().lower()
        hora = _hora_obj(t.get("hora"))
        lat, lng = t.get("lat"), t.get("lng")
        tarea = Tarea.objects.create(
            proyecto=proyecto,
            producto=producto,
            titulo=titulo,
            descripcion=(t.get("detalle") or "").strip()[:500],
            tipo=tipo if tipo in _TIPOS else "tarea",
            prioridad=prioridad if prioridad in _PRIORIDADES else "media",
            asignada_a=asignada,
            fecha_compromiso=_fecha(t.get("fecha"), hoy),
            hora=hora,
            destino_etiqueta=(t.get("lugar") or "").strip()[:200],
            # Un pin a medias no se guarda: o las dos coordenadas o ninguna
            # (misma regla que `TareaForm.clean`).
            destino_lat=lat if lat is not None and lng is not None else None,
            destino_lng=lng if lat is not None and lng is not None else None,
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
