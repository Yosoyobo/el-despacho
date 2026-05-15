from django import template

register = template.Library()

_COLORES = {
    "prospecto": "badge-blue",
    "cotizado": "badge-purple",
    "en_diseno": "badge-warning",
    "revision_cliente": "badge-orange",
    "en_produccion": "badge-warning",
    "entregado": "badge-success",
    "en_pausa": "badge-gray",
    "cancelado": "badge-error",
}


@register.filter(name="color_estado")
def color_estado(estado: str) -> str:
    return _COLORES.get(estado, "badge-gray")
