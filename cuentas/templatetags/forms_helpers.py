"""Template filters auxiliares para formularios (Wave 2 sweep).

Uso en templates:
    {% load forms_helpers %}
    {{ campo|widget_class }}   {# "CheckboxInput" / "DateInput" / etc. #}

`__class__.__name__` no es accesible directamente en templates Django
(prohíbe atributos con guión bajo). Este filtro lo encapsula.
"""

from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def widget_class(bound_field) -> str:
    """Devuelve el nombre de la clase del widget del BoundField."""
    try:
        return bound_field.field.widget.__class__.__name__
    except AttributeError:
        return ""
