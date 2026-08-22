"""La pantalla «El Análisis» — nueve temas del negocio con cifras y lectura.

Las cifras se recalculan en cada visita (son consultas: exactas y gratis). La
lectura del Chalán es la del día; el botón «Analizar ahora» pide una nueva.

Cada quien ve sólo los temas que su permiso alcanza, y dentro del tema del
equipo, sólo las horas de la gente que le toca ver.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from lib.permisos import puede_usar_chalan, puede_ver_analisis


def _gate(request):
    if not puede_ver_analisis(request.user):
        return HttpResponseForbidden("Sin permiso para ver El Análisis.")
    return None


@login_required
def analisis(request):
    from apps.taller_home.analisis import panorama

    if (r := _gate(request)) is not None:
        return r
    datos = panorama(request.user)
    return render(request, "taller_home/analisis.html", {
        **datos,
        "puede_analizar": puede_usar_chalan(request.user),
        "titulo_pagina": "El Análisis",
    })


@login_required
@require_POST
def analizar_ahora(request):
    """Pide una lectura nueva al Chalán. El costo va a quien pica el botón."""
    from apps.taller_home.analisis import generar_lectura

    if (r := _gate(request)) is not None:
        return r
    if not puede_usar_chalan(request.user):
        return HttpResponseForbidden("Sin permiso para usar El Chalán.")

    resultado = generar_lectura(usuario=request.user)
    if resultado.get("ok"):
        creadas = resultado.get("creadas", 0)
        if creadas:
            messages.success(request, f"El Chalán revisó {creadas} temas del negocio.")
        else:
            messages.info(request, "El Chalán no encontró nada nuevo que comentar.")
    else:
        messages.warning(request, resultado.get("error") or "El Chalán no pudo responder.")
    return redirect("taller-analisis")
