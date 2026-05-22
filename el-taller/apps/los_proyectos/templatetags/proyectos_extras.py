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

_COLORES = {
    "por_cotizar": "badge-blue",
    "esperando_respuesta": "badge-orange",
    "en_proceso_diseno": "badge-warning",
    "en_proceso_produccion": "badge-warning",
    "entregado": "badge-success",
    "en_pausa": "badge-gray",
    "cancelado": "badge-error",
}


@register.filter(name="color_estado")
def color_estado(estado: str) -> str:
    return _COLORES.get(estado, "badge-gray")
