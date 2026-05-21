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


@register.simple_tag
def breadcrumb_items(*args):
    """Construye una lista de items para `_breadcrumb.html` a partir de
    pares posicionales label/url. El último item NO debe tener url.

    Uso:
        {% load forms_helpers %}
        {% breadcrumb_items "La Cartera" as items %}
        {% include "_componentes_tailadmin/_breadcrumb.html" with items=items %}

    Para items con url intermedios:
        {% breadcrumb_items "La Cartera" "/cartera/" "Detalle" as items %}
    Pasa pares (label, url) y termina con un label suelto (sin url).
    """
    items = []
    i = 0
    a = list(args)
    while i < len(a):
        label = a[i]
        # Si hay un siguiente arg que parece URL (empieza con /) y no es el último, lo usa como url
        if i + 1 < len(a) and isinstance(a[i + 1], str) and a[i + 1].startswith("/"):
            items.append({"label": label, "url": a[i + 1]})
            i += 2
        else:
            items.append({"label": label})
            i += 1
    return items


@register.filter
def dinero_sin_signo(valor) -> str:
    """Como `dinero` pero sin el `$` adelante (útil dentro de tablas)."""
    formato = dinero(valor)
    if formato.startswith("$"):
        return formato[1:]
    if formato.startswith("-$"):
        return "-" + formato[2:]
    return formato
