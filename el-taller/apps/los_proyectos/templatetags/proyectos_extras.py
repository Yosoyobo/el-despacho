from datetime import date, datetime

from django import template

register = template.Library()


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

_COLORES_FALLBACK = {
    "por_cotizar": "badge-blue",
    "esperando_respuesta": "badge-orange",
    "en_proceso_diseno": "badge-warning",
    "en_proceso_produccion": "badge-warning",
    "entregado": "badge-success",
    "cerrado": "badge-brand",
    "en_pausa": "badge-gray",
    "cancelado": "badge-error",
}


def _mapa_estados():
    """Cache de proceso (60s) del mapa slug → {label, color}.

    Evita N+1 queries en listas/Kanban con muchos badges. Cambios desde
    Gerencia se ven a los ≤60s sin restart. Tolerante a DB no migrada
    (tests aislados, primer boot).
    """
    from django.core.cache import cache
    clave = "proyectos:mapa_estados:v1"
    cacheado = cache.get(clave)
    if cacheado is not None:
        return cacheado
    from apps.los_proyectos.models import EstadoProyecto
    try:
        mapa = {
            e.slug: {"label": e.label, "color": e.color}
            for e in EstadoProyecto.objects.all()
        }
        cache.set(clave, mapa, 60)
        return mapa
    except Exception:
        return {}


def invalidar_mapa_estados():
    """Llamado desde signals al guardar/borrar EstadoProyecto."""
    from django.core.cache import cache
    cache.delete("proyectos:mapa_estados:v1")


@register.filter(name="color_estado")
def color_estado(estado: str) -> str:
    mapa = _mapa_estados()
    if estado in mapa:
        return mapa[estado]["color"]
    return _COLORES_FALLBACK.get(estado, "badge-gray")


# Render-V1: color de TEXTO por token de badge, para la barra de status
# (activo = contorno del color del texto; inactivos al 40% de opacidad).
# Todas estas clases están en el safelist de tailwind.config.js.
_TEXTO_POR_BADGE = {
    "badge-blue": "text-blue-light-600 dark:text-blue-light-400",
    "badge-brand": "text-brand-600 dark:text-brand-400",
    "badge-orange": "text-orange-600 dark:text-orange-400",
    "badge-warning": "text-warning-600 dark:text-warning-400",
    "badge-success": "text-success-600 dark:text-success-400",
    "badge-error": "text-error-600 dark:text-error-400",
    "badge-gray": "text-gray-600 dark:text-gray-300",
    "badge-purple": "text-purple-600 dark:text-purple-400",
}


@register.filter(name="estado_text_clase")
def estado_text_clase(color_badge: str) -> str:
    """Clase(s) de color de texto para un token de badge de estado."""
    return _TEXTO_POR_BADGE.get(color_badge, "text-gray-600 dark:text-gray-300")


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
