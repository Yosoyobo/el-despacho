"""Filtros de template para los estados del Buzón (S-Buzon-Estados-V1).

Disponibles en El Taller y La Gerencia porque `buzon` es app shared.
"""

from django import template

from buzon.estados import color_de, label_de

register = template.Library()


@register.filter(name="color_estado_buzon")
def color_estado_buzon(slug: str) -> str:
    """Color HEX del estado del Buzón. Se inyecta en la custom property --ec."""
    return color_de(slug or "")


@register.filter(name="estado_label_buzon")
def estado_label_buzon(slug: str) -> str:
    """Label visible del estado (configurable desde Gerencia)."""
    return label_de(slug or "")
