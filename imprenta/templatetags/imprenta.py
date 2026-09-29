"""Filtros de las plantillas de La Imprenta."""

from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def rayado(estilo, contador) -> str:
    """El fondo de un renglón alternado: `{{ e|rayado:forloop.counter }}`.

    Vacío si el rayado está apagado, que es el documento de siempre.
    """
    try:
        return estilo.fila(contador)
    except AttributeError:
        return ""
