"""Vistas de El Checador (El Taller) — móvil-first.

E2: tablero con botón Entrada/Salida + snapshot geo + Mi semana.
"""

from __future__ import annotations

import datetime
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from lib.permisos import puede_checar

from . import services
from .models import Jornada


def _requiere_checar(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not puede_checar(request.user):
            return HttpResponseForbidden("Sin acceso a El Checador.")
        return view(request, *args, **kwargs)
    return inner


def _geo_de_request(request) -> dict:
    """Arma el dict geo desde el POST. Si falta o el cliente reporta `sin_geo`,
    devuelve `{"sin_geo": True}` (la checada se registra igual)."""
    if request.POST.get("sin_geo") == "1":
        return {"sin_geo": True}
    lat = request.POST.get("lat")
    lng = request.POST.get("lng")
    if not lat or not lng:
        return {"sin_geo": True}
    try:
        precision = request.POST.get("precision")
        return {
            "lat": float(lat),
            "lng": float(lng),
            "precision": float(precision) if precision else None,
            "sin_geo": False,
        }
    except (TypeError, ValueError):
        return {"sin_geo": True}


@login_required
@_requiere_checar
def tablero(request):
    hoy = timezone.localdate()
    jornada = Jornada.objects.filter(usuario=request.user, fecha=hoy).first()

    if jornada is None or not jornada.entrada_en:
        accion = "entrada"
    elif not jornada.salida_en:
        accion = "salida"
    else:
        accion = "completa"

    desde = hoy - datetime.timedelta(days=6)
    semana = list(
        Jornada.objects.filter(usuario=request.user, fecha__gte=desde, fecha__lte=hoy).order_by("-fecha"),
    )

    return render(request, "checador/tablero.html", {
        "jornada": jornada,
        "accion": accion,
        "semana": semana,
        "hoy": hoy,
    })


@login_required
@_requiere_checar
@require_POST
def checar(request):
    accion = request.POST.get("accion", "entrada")
    geo = _geo_de_request(request)
    uuid = (request.POST.get("uuid") or "")[:64]

    try:
        if accion == "salida":
            services.checar_salida(request.user, geo=geo, uuid=uuid)
            messages.success(request, "Registramos tu salida. ¡Buen descanso!")
        else:
            jornada = services.checar_entrada(request.user, geo=geo, uuid=uuid)
            if jornada.retardo_min:
                messages.warning(request, f"Entrada registrada con {jornada.retardo_min} min de retardo.")
            else:
                messages.success(request, "Entrada registrada. ¡A tiempo!")
        if geo.get("sin_geo"):
            messages.info(request, "Se registró sin ubicación (GPS no disponible).")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("checador:tablero")
