"""La tarea rápida de la tarjeta de producto: «@persona» + Enter (LC 2026-09-28).

Oscar: «@persona crea una tarea ligada al producto», **en el campo de tareas del
producto, directo, sin IA**; fecha: la que se escriba o, si no, la entrega del
proyecto. Es el camino de un toque; el de «🤖 Dictar tareas» (con El Chalán,
preview y confirmación) sigue al lado para lo que necesita interpretarse.

Por qué sin IA no es un atajo peligroso: aquí no se interpreta nada. La persona
sale de una mención explícita que se elige de la lista (o que se resuelve SÓLO si
no hay duda), la fecha de un reconocedor determinista (`lib.fecha.fecha_en_texto`)
y el título es literalmente lo que se escribió. Nada se adivina:

- dos personas que coinciden con la mención ⇒ no se crea y se dice quiénes;
- una mención que no es de nadie ⇒ no se crea y se dice;
- sin texto además de la mención ⇒ no se crea (una tarea sin qué hacer no sirve).
"""

from __future__ import annotations

import contextlib
import re
import unicodedata

# «@jorge», «@jorge-berebichez», «@karla_m». No empata el @ de un correo
# («foo@bar.com»): antes del @ no puede haber letra ni número.
_RE_MENCION = re.compile(r"(?<![\w@])@([A-Za-z0-9_][A-Za-z0-9_.-]*[A-Za-z0-9_]|[A-Za-z0-9_])")

_MAX_TITULO = 200


def _plano(texto) -> str:
    crudo = "" if texto is None else str(texto)
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", crudo) if unicodedata.category(c) != "Mn")
    return " ".join(sin_acentos.lower().split())


def menciones(texto: str) -> list[str]:
    """Los handles mencionados, en orden y sin repetir."""
    vistos: list[str] = []
    for m in _RE_MENCION.finditer(texto or ""):
        h = m.group(1)
        if h.lower() not in {v.lower() for v in vistos}:
            vistos.append(h)
    return vistos


def resolver_mencion(handle: str):
    """`(usuario, error)`. Por etapas, de la más exacta a la más laxa, y en cada
    una sólo cuenta si es INEQUÍVOCA: con dos que coinciden no se adivina."""
    from cuentas.models.usuario import Usuario

    h = (handle or "").strip().lstrip("@")
    if not h:
        return None, "Falta a quién le toca."
    activos = list(Usuario.objects.filter(is_active=True).order_by("nombre_completo"))
    buscado = _plano(h.replace("-", " ").replace("_", " ").replace(".", " "))

    def _nombre(u) -> str:
        return _plano(u.nombre_completo or "")

    etapas = (
        [u for u in activos if (u.slug or "").lower() == h.lower()],
        [u for u in activos if _nombre(u) == buscado],
        [u for u in activos if (u.slug or "").lower().startswith(h.lower())],
        [u for u in activos if _nombre(u).split(" ")[:1] == [buscado]],
        [u for u in activos if buscado and _nombre(u).startswith(buscado)],
    )
    for coincidencias in etapas:
        if len(coincidencias) == 1:
            return coincidencias[0], ""
        if len(coincidencias) > 1:
            nombres = ", ".join(u.nombre_completo or u.email for u in coincidencias[:4])
            return None, (f"@{h} coincide con {len(coincidencias)} personas ({nombres}). "
                          "Elígela de la lista para que no haya duda.")
    return None, f"No encontré a nadie que se llame @{h}."


def _titulo(texto: str) -> str:
    """Lo que queda del texto, limpio: sin puntuación suelta en las orillas y con
    mayúscula inicial. No se reescribe nada más."""
    limpio = " ".join((texto or "").split()).strip(" ,.;:-–—·")
    if not limpio:
        return ""
    return (limpio[0].upper() + limpio[1:])[:_MAX_TITULO]


def _fecha_de_entrega(proyecto):
    """La fecha de entrega del proyecto como `date` en hora local (el campo es un
    datetime aware; leerle `.date()` en UTC daría el día equivocado de noche)."""
    entrega = getattr(proyecto, "fecha_compromiso", None)
    if entrega is None:
        return None
    try:
        from django.utils import timezone

        return timezone.localtime(entrega).date() if timezone.is_aware(entrega) else entrega.date()
    except Exception:  # noqa: BLE001
        return getattr(entrega, "date", lambda: None)()


def crear_desde_texto(*, proyecto, producto, texto: str, usuario) -> dict:
    """Crea la tarea ligada a `producto` a partir de «@persona qué hacer [cuándo]».

    Devuelve `{ok, tarea, error, fecha_de_entrega}`. Re-valida el permiso (defensa
    en profundidad: la vista ya lo checó) y nunca lanza por un texto raro.
    """
    from apps.el_pizarron.models import Tarea

    from lib.fecha import fecha_en_texto
    from lib.permisos import puede_editar_proyecto

    if not puede_editar_proyecto(usuario, proyecto):
        return {"ok": False, "tarea": None, "error": "Sin permiso para editar el proyecto."}
    if producto is None or producto.proyecto_id != proyecto.pk:
        return {"ok": False, "tarea": None, "error": "Ese producto no es de este proyecto."}

    crudo = (texto or "").strip()
    handles = menciones(crudo)
    if not handles:
        return {"ok": False, "tarea": None,
                "error": "Escribe @ y elige a quién le toca; luego Enter."}

    personas = []
    for h in handles:
        persona, error = resolver_mencion(h)
        if error:
            return {"ok": False, "tarea": None, "error": error}
        if persona not in personas:
            personas.append(persona)

    sin_menciones = _RE_MENCION.sub(" ", crudo)
    fecha, resto = fecha_en_texto(sin_menciones)
    titulo = _titulo(resto)
    if not titulo:
        return {"ok": False, "tarea": None,
                "error": "¿Qué hay que hacer? Escribe la tarea además de la @persona."}

    de_entrega = fecha is None
    if de_entrega:
        fecha = _fecha_de_entrega(proyecto)

    tarea = Tarea.objects.create(
        proyecto=proyecto,
        producto=producto,
        titulo=titulo,
        asignada_a=personas[0],
        fecha_compromiso=fecha,
        creado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
    )
    if len(personas) > 1:
        tarea.responsables.set(personas[1:])
    _notificar(tarea, proyecto, usuario)
    return {"ok": True, "tarea": tarea, "error": "", "fecha_de_entrega": de_entrega}


def _notificar(tarea, proyecto, usuario) -> None:
    """Evento + push + actividad, igual que el alta manual. Best-effort."""
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz

        emitir(EventoPortavoz(
            tipo="tarea.creada",
            actor_id=getattr(usuario, "pk", None),
            actor_email=getattr(usuario, "email", None),
            payload={"tarea_id": tarea.pk, "proyecto_id": proyecto.pk,
                     "producto_id": tarea.producto_id, "origen": "tarjeta_producto"},
        ))
    with contextlib.suppress(Exception):
        from apps.taller_home.push_handlers import notificar_tarea_asignada

        notificar_tarea_asignada(tarea, usuario)
    with contextlib.suppress(Exception):
        from . import servicios_actividad

        servicios_actividad.registrar(
            proyecto=proyecto, tipo="tarea_creada",
            descripcion=f"Nueva tarea «{tarea.titulo[:60]}»", actor=usuario,
            url=f"/proyectos/{proyecto.pk}/",
        )


__all__ = ["crear_desde_texto", "menciones", "resolver_mencion"]
