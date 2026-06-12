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
from .models import Jornada, Visita


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
    visitas_hoy = list(
        Visita.objects.filter(usuario=request.user, registrado_en__date=hoy)
        .select_related("cliente", "proveedor").order_by("-registrado_en"),
    )

    return render(request, "checador/tablero.html", {
        "jornada": jornada,
        "accion": accion,
        "semana": semana,
        "visitas_hoy": visitas_hoy,
        "hoy": hoy,
    })


@login_required
@_requiere_checar
def visita_modal(request):
    """GET HTMX → fragmento del modal para registrar una visita."""
    from apps.el_catalogo.models import Proveedor
    from apps.la_cartera.models import Cliente
    return render(request, "checador/_modal_visita.html", {
        "clientes": Cliente.objects.filter(activo=True).order_by("razon_social"),
        "proveedores": Proveedor.objects.filter(activo=True).order_by("razon_social"),
    })


@login_required
@_requiere_checar
@require_POST
def visita(request):
    from apps.el_catalogo.models import Proveedor
    from apps.la_cartera.models import Cliente

    tipo = request.POST.get("tipo", "cliente")
    nota = (request.POST.get("nota") or "").strip()
    geo = _geo_de_request(request)
    uuid = (request.POST.get("uuid") or "")[:64]

    cliente = proveedor = None
    if tipo == "cliente":
        cid = request.POST.get("cliente")
        cliente = Cliente.objects.filter(pk=cid).first() if cid else None
    elif tipo == "proveedor":
        pid = request.POST.get("proveedor")
        proveedor = Proveedor.objects.filter(pk=pid).first() if pid else None

    try:
        services.registrar_visita(
            request.user, tipo=tipo, cliente=cliente, proveedor=proveedor,
            geo=geo, nota=nota, uuid=uuid,
        )
        messages.success(request, "Visita registrada.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("checador:tablero")


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
