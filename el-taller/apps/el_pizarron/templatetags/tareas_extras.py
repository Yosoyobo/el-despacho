"""Filtros de estados de tarea (S-LC-Feedback-V6 Bloque 1).

Espejo de `proyectos_extras`: labels y colores leen de EstadoTarea
(configurable desde Gerencia) vía cache de proceso 60s. "Atrasada" se pinta
amarillo encima de cualquier estado no terminal vencido.
"""

from apps.el_pizarron.models.estado_tarea import mapa_estados_tarea
from apps.el_pizarron.models.tarea import ESTADOS_TAREA, TIPOS_TAREA
from django import template

register = template.Library()

# Amarillo warning — color fijo del derivado "Atrasada" (coherente con el
# bloque de fecha del Dashboard).
COLOR_ATRASADA = "#f79009"

_COLORES_FALLBACK = {
    "pendiente": "#0ba5ec",
    "en_curso": "#465fff",
    "completada": "#12b76a",
}

_EMOJI_TIPO = {
    "tarea": "✓",
    "entrega": "📦",
    "junta": "📅",
    "recoger": "🚚",
}


@register.filter(name="color_estado_tarea")
def color_estado_tarea(estado: str) -> str:
    """Color HEX del estado de tarea (se inyecta en la custom property --ec)."""
    mapa = mapa_estados_tarea()
    if estado in mapa:
        return mapa[estado]["color"]
    return _COLORES_FALLBACK.get(estado, "#667085")


@register.filter(name="estado_label_tarea")
def estado_label_tarea(estado: str) -> str:
    """Label visible del estado de tarea (configurable desde Gerencia)."""
    mapa = mapa_estados_tarea()
    if estado in mapa:
        return mapa[estado]["label"]
    return dict(ESTADOS_TAREA).get(estado, estado)


@register.filter(name="color_estado_tarea_de")
def color_estado_tarea_de(tarea) -> str:
    """Color efectivo de UNA tarea: amarillo si está atrasada, si no el del estado."""
    if getattr(tarea, "esta_atrasada", False):
        return COLOR_ATRASADA
    return color_estado_tarea(tarea.estado)


@register.filter(name="estado_visible_tarea")
def estado_visible_tarea(tarea) -> str:
    """Label efectivo de UNA tarea: 'Atrasada' si venció sin cerrar, si no su estado."""
    if getattr(tarea, "esta_atrasada", False):
        return "Atrasada"
    return estado_label_tarea(tarea.estado)


@register.filter(name="tipo_tarea_label")
def tipo_tarea_label(tipo: str) -> str:
    return dict(TIPOS_TAREA).get(tipo, tipo or "Tarea")


@register.filter(name="tipo_tarea_emoji")
def tipo_tarea_emoji(tipo: str) -> str:
    return _EMOJI_TIPO.get(tipo, "✓")


@register.inclusion_tag("pizarron/_bloque_fecha.html")
def bloque_fecha(fecha):
    """Bloque de fecha de 'Mis tareas' (V6 Bloque 3): día de la semana arriba,
    número en medio, mes abajo. HOY/MAÑANA reemplazan el bloque; las fechas
    pasadas se pintan en amarillo (coherente con 'Atrasada')."""
    from django.utils import timezone
    hoy = timezone.localdate()
    es_hoy = es_manana = es_pasada = False
    if fecha:
        es_hoy = fecha == hoy
        es_manana = (fecha - hoy).days == 1
        es_pasada = fecha < hoy
    return {
        "fecha": fecha,
        "es_hoy": es_hoy,
        "es_manana": es_manana,
        "es_pasada": es_pasada,
    }
