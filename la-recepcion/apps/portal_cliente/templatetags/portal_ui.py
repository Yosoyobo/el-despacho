"""Filtros de presentación de La Recepción.

Las clases completas viven aquí (y `tailwind.config.js` lee este archivo) para
que Tailwind las encuentre: una clase armada a pedazos en la plantilla no se
compila.
"""

from __future__ import annotations

from django import template

register = template.Library()

_TONOS = {
    "azul": "bg-blue-light-50 text-blue-light-700 dark:bg-blue-light-500/15 dark:text-blue-light-300",
    "ambar": "bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-300",
    "marca": "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
    "verde": "bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-300",
    "rojo": "bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-300",
    "gris": "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
}


@register.filter
def tono(nombre: str) -> str:
    """`{{ p.tono|tono }}` → las clases del chip de ese tono."""
    return _TONOS.get(nombre or "", _TONOS["gris"])


@register.filter
def paso_clase(paso_actual: int, indice: int) -> str:
    """Clases de un paso del ciclo (1-4) según el paso en que va el proyecto."""
    try:
        actual, i = int(paso_actual), int(indice)
    except (TypeError, ValueError):
        actual, i = 0, 0
    if actual and i < actual:
        return "bg-success-500"
    if actual and i == actual:
        return "bg-brand-500"
    return "bg-gray-200 dark:bg-gray-700"
