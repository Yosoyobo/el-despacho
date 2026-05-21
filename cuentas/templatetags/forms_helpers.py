"""Template filters auxiliares (Wave 2 sweep + S-UX-Dummy-Proof).

Uso en templates:
    {% load forms_helpers %}
    {{ campo|widget_class }}   {# "CheckboxInput" / "DateInput" / etc. #}
    {{ valor|dinero }}          {# "$1,234.56" / "—" si null #}
    {{ valor|dinero_sin_signo }} {# "1,234.56" #}
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def widget_class(bound_field) -> str:
    """Devuelve el nombre de la clase del widget del BoundField."""
    try:
        return bound_field.field.widget.__class__.__name__
    except AttributeError:
        return ""


@register.filter
def dinero(valor) -> str:
    """Formatea un monto como `$1,234.56`. None / vacío → `—`."""
    if valor is None or valor == "":
        return "—"
    try:
        v = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return str(valor)
    signo = "-" if v < 0 else ""
    entero, _, decimales = abs(v).__format__("f").partition(".")
    grupos = []
    while len(entero) > 3:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]
    if entero:
        grupos.insert(0, entero)
    return f"{signo}${','.join(grupos)}.{decimales or '00':<02}"[:32]


@register.filter
def dinero_sin_signo(valor) -> str:
    """Como `dinero` pero sin el `$` adelante (útil dentro de tablas)."""
    formato = dinero(valor)
    if formato.startswith("$"):
        return formato[1:]
    if formato.startswith("-$"):
        return "-" + formato[2:]
    return formato
