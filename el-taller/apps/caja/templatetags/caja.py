"""`{% load caja %}` — los botones de La Caja en plantillas de otros módulos.

    {% boton_link_libre cliente=cliente %}
    {% boton_link_libre proyecto=proyecto clase="text-xs font-medium text-brand-600" texto="Cobrar con link" %}

Sale vacío si La Caja está apagada o si quien mira no puede crear links.
"""

from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def boton_link_libre(context, cliente=None, proyecto=None, clase="btn-secundario", texto="💳 Cobrar con link"):
    from apps.caja.ui import boton_libre

    request = context.get("request")
    user = getattr(request, "user", None)
    return mark_safe(boton_libre(user, cliente=cliente, proyecto=proyecto, clase=clase, texto=texto))  # noqa: S308 — format_html ya escapó


@register.simple_tag(takes_context=True)
def boton_link_pago(context, objeto, clase="btn-secundario"):
    from apps.caja.ui import boton_accion

    request = context.get("request")
    user = getattr(request, "user", None)
    return mark_safe(boton_accion(user, objeto, clase=clase))  # noqa: S308 — format_html ya escapó
