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
def tiene_rol(user, nombres: str) -> bool:
    """V6 Bloque 10: check de rol en templates que reconoce rol primario +
    roles personalizados (roles_extra). Uso:
    `{% if request.user|tiene_rol:"super_admin,dueno" %}`.
    Reemplaza a los `request.user.rol == "x"` duros que ignoraban roles_extra."""
    try:
        from lib.permisos import roles_efectivos
        pedidos = {n.strip() for n in (nombres or "").split(",") if n.strip()}
        return bool(roles_efectivos(user) & pedidos)
    except Exception:  # noqa: BLE001 — un check de UI nunca tumba el render
        return False


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
def miles(valor) -> str:
    """Formatea un entero con separador de miles: `55582` → `55,582`. None /
    vacío → `0`. Para tokens y conteos (sin decimales)."""
    if valor is None or valor == "":
        return "0"
    try:
        n = int(valor)
    except (ValueError, TypeError):
        return str(valor)
    signo = "-" if n < 0 else ""
    entero = str(abs(n))
    grupos = []
    while len(entero) > 3:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]
    if entero:
        grupos.insert(0, entero)
    return f"{signo}{','.join(grupos)}"


@register.filter
def costo_ia(valor) -> str:
    """Costo de IA: 4 decimales con `$`, o `< $0.001` para montos diminutos
    no nulos. `$0.0365`, `< $0.001`, `$0.0000` para cero."""
    from decimal import Decimal as _D
    if valor is None or valor == "":
        return "—"
    try:
        v = _D(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return str(valor)
    if v > 0 and v < _D("0.001"):
        return "< $0.001"
    return f"${v.quantize(_D('0.0001'))}"


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


@register.filter
def dinero_corto(valor) -> str:
    """Como `dinero` pero oculta los centavos cuando son .00.
    `95` → `$95`; `95.5` → `$95.50`. Para subtítulos compactos (Oscar V-feedback:
    precio unitario en '$95 x 10 pz' sin .00 salvo que haya centavos)."""
    formato = dinero(valor)
    if formato.endswith(".00"):
        return formato[:-3]
    return formato


# Abreviaturas en español capitalizadas (no dependemos de la locale de Django,
# que las da en minúsculas con punto). Lunes=0.
_DIAS_ABR = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
_MESES_ABR = ("Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


@register.filter
def fecha_corta(valor) -> str:
    """Fecha legible en español: `Vie 26 Jun 2026` (día de semana + día + mes + año).

    Acepta `date`/`datetime`; None/"" → `—`. Usado en la lista de Cotizaciones
    (reporte LC: fecha formateada en lugar de ISO)."""
    if valor is None or valor == "":
        return "—"
    try:
        dia_semana = _DIAS_ABR[valor.weekday()]
        return f"{dia_semana} {valor.day:02d} {_MESES_ABR[valor.month - 1]} {valor.year}"
    except (AttributeError, IndexError, TypeError):
        return str(valor)
