"""Filtro `hfmt` — formatea horas según la preferencia del usuario (24h/AM-PM).

Se registra como `builtin` en los 3 settings, así está disponible en TODAS las
plantillas sin `{% load %}`. Reemplaza a `|date:"…H:i…"` y `|time:"H:i"`:
el formato se pasa igual, pero la porción de hora se ajusta a la preferencia
(ver lib.formato_hora).

    {{ jornada.entrada_en|hfmt:"H:i" }}        → "14:30" o "2:30 p.m."
    {{ msg.creado_en|hfmt:"Y-m-d H:i" }}       → "2026-06-15 14:30" o "… 2:30 p.m."
"""

from __future__ import annotations

from django import template
from django.template.defaultfilters import date as _date

from lib.formato_hora import aplicar

register = template.Library()


# `expects_localtime=True`: igual que los filtros nativos `date`/`time`, hace que
# Django convierta los datetime aware (guardados en UTC) a la zona activa
# (America/Mexico_City) ANTES de formatear. Sin esto, `hfmt` mostraba la hora en
# UTC → +6h en El Checador, el historial del Dictado y demás (bug 2026-06-16).
@register.filter(name="hfmt", expects_localtime=True)
def hfmt(value, fmt: str = "H:i"):
    if value in (None, ""):
        return ""
    return _date(value, aplicar(fmt))
