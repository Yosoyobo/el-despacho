from django import template

register = template.Library()

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
