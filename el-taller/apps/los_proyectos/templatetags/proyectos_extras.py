import json
from datetime import date, datetime

from django import template
from django.utils import formats
from django.utils.safestring import mark_safe

from .. import colores

register = template.Library()


@register.filter(name="nombre_cliente")
def nombre_cliente(proyecto):
    """Decisión Oscar: en widgets/listas el protagonista es el NOMBRE del
    proyecto + el NOMBRE del cliente (en esa prioridad), no el código LC-NNNN.

    Devuelve "Nombre · Cliente" tolerando nulos (proyecto, cliente, campos
    vacíos). Si no hay proyecto, devuelve "". Si falta el cliente, devuelve
    solo el nombre del proyecto (con fallback al código si tampoco hay nombre).
    """
    if not proyecto:
        return ""
    nombre = (getattr(proyecto, "nombre", "") or "").strip()
    cliente = getattr(proyecto, "cliente", None)
    razon = (getattr(cliente, "razon_social", "") or "").strip() if cliente else ""
    if not nombre:
        nombre = (getattr(proyecto, "codigo", "") or "").strip()
    if nombre and razon:
        return f"{nombre} · {razon}"
    return nombre or razon


@register.filter(name="dentro_de")
def dentro_de(fecha):
    """Devuelve 'dentro de N días' / 'hoy' / 'vencido hace N días' para una fecha."""
    if not fecha:
        return "—"
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    hoy = date.today()
    delta = (fecha - hoy).days
    if delta == 0:
        return "hoy"
    if delta == 1:
        return "mañana"
    if delta == -1:
        return "ayer"
    if delta > 0:
        return f"en {delta} días"
    return f"vencido hace {-delta} días"


def _es_terminal(slug: str) -> bool:
    """¿El estado cierra el proyecto? Lee del mapa cacheado (sin N+1)."""
    mapa = _mapa_estados()
    if slug in mapa and "terminal" in mapa[slug]:
        return bool(mapa[slug]["terminal"])
    from apps.los_proyectos.models.proyecto import ESTADOS_TERMINALES
    return slug in ESTADOS_TERMINALES


def _fecha_entrega(proyecto):
    """La fecha con la que se cerró: la real si se capturó, si no el compromiso."""
    return getattr(proyecto, "fecha_real_entrega", None) or proyecto.fecha_compromiso


@register.filter(name="compromiso_nota")
def compromiso_nota(proyecto) -> str:
    """Nota relativa del compromiso para LISTAS (que ya muestran la fecha arriba).

    LC 2026-07-25 (Oscar): un proyecto entregado, cerrado o cancelado ya no dice
    «vencido hace N días» — no tiene sentido correrle el reloj a algo terminado.
    En esos estados la nota queda vacía y solo se ve la fecha.
    """
    if not proyecto or not proyecto.fecha_compromiso:
        return ""
    if _es_terminal(getattr(proyecto, "estado", "")):
        return ""
    return dentro_de(proyecto.fecha_compromiso)


@register.filter(name="compromiso_kanban")
def compromiso_kanban(proyecto) -> str:
    """Texto de fecha para la tarjeta del Kanban (una sola línea).

    - entregado → «entregado 12 Jul 2026»
    - otro terminal (cerrado/cancelado) → solo la fecha
    - activo → nota relativa («en 3 días», «vencido hace 2 días»)
    """
    if not proyecto:
        return "—"
    estado = getattr(proyecto, "estado", "")
    if estado == "entregado":
        f = _fecha_entrega(proyecto)
        return f"entregado {formats.date_format(f, 'd M Y')}" if f else "entregado"
    if _es_terminal(estado):
        f = _fecha_entrega(proyecto)
        return formats.date_format(f, "d M Y") if f else "—"
    return dentro_de(proyecto.fecha_compromiso)


@register.filter(name="compromiso_clase")
def compromiso_clase(proyecto) -> str:
    """Color del texto de fecha. Los terminales van en gris (sin alarma)."""
    if not proyecto:
        return "text-gray-400"
    if _es_terminal(getattr(proyecto, "estado", "")):
        return "text-gray-500 dark:text-gray-400"
    return dentro_de_clase(proyecto.fecha_compromiso)


@register.filter(name="dentro_de_clase")
def dentro_de_clase(fecha):
    """Color del texto según urgencia: rojo si vencido, naranja ≤3d, gris."""
    if not fecha:
        return "text-gray-400"
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    delta = (fecha - date.today()).days
    if delta < 0:
        return "text-error-600 dark:text-error-400 font-medium"
    if delta <= 3:
        return "text-warning-600 dark:text-warning-400 font-medium"
    return "text-gray-600 dark:text-gray-300"

# S-Estados-Color-HEX: el color del estado es un HEX libre. El fallback
# (estados legacy sin fila en DB) usa la paleta TailAdmin canónica.
_COLORES_FALLBACK = {
    "por_cotizar": "#0ba5ec",
    "esperando_respuesta": "#fb6514",
    "en_proceso_diseno": "#f79009",
    "en_proceso_produccion": "#f79009",
    "entregado": "#12b76a",
    "cerrado": "#465fff",
    "en_pausa": "#667085",
    "cancelado": "#f04438",
}


def _mapa_estados():
    """Cache de proceso (60s) del mapa slug → {label, color}.

    Evita N+1 queries en listas/Kanban con muchos badges. Cambios desde
    Gerencia se ven a los ≤60s sin restart. Tolerante a DB no migrada
    (tests aislados, primer boot).
    """
    from django.core.cache import cache
    # v3: el mapa incluye `terminal` (LC 2026-07-25) y `activo` (para que un
    # estado oculto en Gerencia desaparezca de los filtros).
    clave = "proyectos:mapa_estados:v3"
    cacheado = cache.get(clave)
    if cacheado is not None:
        return cacheado
    from apps.los_proyectos.models import EstadoProyecto
    try:
        mapa = {
            e.slug: {"label": e.label, "color": e.color,
                     "terminal": e.terminal, "activo": e.activo}
            for e in EstadoProyecto.objects.all()
        }
        cache.set(clave, mapa, 60)
        return mapa
    except Exception:
        return {}


def invalidar_mapa_estados():
    """Llamado desde signals al guardar/borrar EstadoProyecto."""
    from django.core.cache import cache
    cache.delete_many([
        "proyectos:mapa_estados:v3",
        "proyectos:mapa_estados:v2",
        "proyectos:mapa_estados:v1",
    ])


def estado_visible(slug: str) -> bool:
    """¿El estado sigue ofreciéndose como filtro?

    Oscar 2026-07-25: al ocultar un estado desde Gerencia debe desaparecer de
    las pastillas/selectores de la página correspondiente. Un slug que no vive
    en el catálogo (legacy) siempre se considera visible.
    """
    entrada = _mapa_estados().get(slug)
    return True if entrada is None else bool(entrada.get("activo", True))


@register.filter(name="color_estado")
def color_estado(estado: str) -> str:
    """Color HEX del estado (#RRGGBB). Se inyecta en la custom property --ec."""
    mapa = _mapa_estados()
    if estado in mapa:
        return mapa[estado]["color"]
    return _COLORES_FALLBACK.get(estado, "#667085")


@register.filter(name="estado_label")
def estado_label(estado: str) -> str:
    """Label visible del estado (configurable desde Gerencia)."""
    mapa = _mapa_estados()
    if estado in mapa:
        return mapa[estado]["label"]
    for slug, label in (
        ("por_cotizar", "Por cotizar"),
        ("esperando_respuesta", "Esperando respuesta"),
        ("en_proceso_diseno", "En proceso de diseño"),
        ("en_proceso_produccion", "En proceso de producción"),
        ("entregado", "Entregado"),
        ("cerrado", "Cerrado"),
        ("en_pausa", "En pausa"),
        ("cancelado", "Cancelado"),
    ):
        if slug == estado:
            return label
    return estado


# LC 2026-08-04 (Oscar): «que dejen de cambiar de color cada toggle o
# movimiento». El color de la tarjeta de producto se rotaba con `{% cycle %}`,
# es decir por POSICIÓN: al arrastrar una tarjeta o apagar un toggle (que la
# movía de lugar) TODAS se recoloreaban.
#
# LC 2026-08-18 (Oscar): «los necesito 100% variados y contrastados, y
# sólidamente ligados a cada uno de sus productos. Si en el nombre o descripción
# se menciona un color, usar ese». El color ya no es un token de Tailwind sino un
# HEX que sale de `apps.los_proyectos.colores` y se pinta con `--ec` +
# `color-mix`. La regla completa vive en `ProyectoProducto.color_efectivo`.


@register.filter(name="color_tarjeta")
def color_tarjeta(linea) -> str:
    """HEX con el que se pinta la tarjeta de un producto del proyecto.

    Recibe la LÍNEA (`ProyectoProducto` o su foto por versión). Si le llega otra
    cosa —un texto, un nulo— devuelve un color estable derivado de ella, para que
    una tarjeta todavía sin guardar nunca aparezca sin identidad.
    """
    efectivo = getattr(linea, "color_efectivo", None)
    if efectivo:
        return efectivo
    if linea in (None, ""):
        return colores.COLOR_DEFAULT
    return colores.color_estable(str(linea))


@register.filter(name="color_escala")
def color_escala(indice) -> str:
    """HEX de la opción de volumen número `indice` (0 = la B, la primera).

    LC 2026-08-18 (Oscar): «las opciones (B) (C) etc deben de tener cada una otro
    color, empezando con el azul que ya tienes» — y el azul de la casa es
    justamente el primero de la lista.
    """
    try:
        n = int(indice)
    except (TypeError, ValueError):
        n = 0
    return colores.PALETA[max(0, n) % len(colores.PALETA)]


@register.simple_tag(name="colores_palabras_json")
def colores_palabras_json() -> str:
    """Los colores nombrados, para que la tarjeta se recolore mientras escribes.

    Se sirve desde aquí —y no desde cada vista— para que el mapa siga teniendo
    UN solo dueño: `apps.los_proyectos.colores`.
    """
    pares = [[list(palabras), hexa] for palabras, hexa in colores.COLORES_NOMBRADOS]
    return mark_safe(json.dumps(pares, ensure_ascii=False))  # noqa: S308 — datos propios


@register.simple_tag(name="colores_paleta_json")
def colores_paleta_json() -> str:
    """La lista de colores, para que el JS reparta las opciones B, C… igual."""
    return mark_safe(json.dumps(list(colores.PALETA)))  # noqa: S308 — datos propios
