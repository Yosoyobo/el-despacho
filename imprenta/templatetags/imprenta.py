"""Filtros de las plantillas de La Imprenta."""

from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def fecha_larga(valor) -> str:
    """`{{ p.fecha_compromiso|fecha_larga }}` → «lunes 1 de diciembre de 2025».

    Delgado a propósito: la lógica (y los nombres en español) viven en
    `lib.fecha.fecha_larga`, que no depende del idioma del servidor.
    """
    from lib.fecha import fecha_larga as _larga

    return _larga(valor)


@register.filter
def rayado(estilo, contador) -> str:
    """El fondo de un renglón alternado: `{{ e|rayado:forloop.counter }}`.

    Vacío si el rayado está apagado, que es el documento de siempre.
    """
    try:
        return estilo.fila(contador)
    except AttributeError:
        return ""
