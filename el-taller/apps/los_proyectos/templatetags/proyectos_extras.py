from django import template

register = template.Library()

_COLORES = {
    "prospecto": "badge-blue",
    "cotizado": "badge-purple",
    "en_diseno": "badge-amber",
    "revision_cliente": "badge-orange",
    "en_produccion": "badge-amber",
    "entregado": "badge-emerald",
    "en_pausa": "badge-slate",
    "cancelado": "badge-rose",
}


@register.filter(name="color_estado")
def color_estado(estado: str) -> str:
    return _COLORES.get(estado, "badge-slate")
