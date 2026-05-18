"""Los Chalanes (admin) — UI mínima funcional.

3 secciones en una sola página:
- El Cuadro: tabla de estaciones, cada fila editable inline (POST guardar_cuadro).
- La Cadena: lista ordenada con botones up/down (POST reordenar) y toggle (POST toggle_activo).
- La Auditoría: últimos 50 intentos de analistas_log.

Solo super_admin puede modificar; dueño puede ver auditoría.
"""

from __future__ import annotations

import contextlib

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ajustes.models.analistas_log import AnalistaLog
from chalanes.models import CadenaFallback, CuadroChalanes
from lib.permisos import requires_role
from lib.portavoz import emitir


@requires_role("super_admin", "dueno")
def panel(request):
    cuadro = CuadroChalanes.objects.all().order_by("estacion")
    cadena = CadenaFallback.objects.all().order_by("prioridad")
    logs = AnalistaLog.objects.all().order_by("-creado_en")[:50]
    return render(request, "los_chalanes/panel.html", {
        "cuadro": cuadro,
        "cadena": cadena,
        "logs": logs,
        "puede_modificar": request.user.rol == "super_admin",
    })


@require_POST
@requires_role("super_admin")
def guardar_cuadro(request):
    estacion = request.POST.get("estacion") or ""
    proveedor = request.POST.get("proveedor") or ""
    modelo = request.POST.get("modelo") or ""
    fila = CuadroChalanes.objects.filter(estacion=estacion).first()
    if not fila:
        messages.error(request, f"Estación desconocida: {estacion}")
        return redirect("los_chalanes:panel")
    fila.proveedor = proveedor
    fila.modelo = modelo
    fila.actualizado_por = request.user
    fila.save()
    with contextlib.suppress(Exception):
        emitir({"tipo": "chalanes.cuadro_actualizado", "estacion": estacion,
                "proveedor": proveedor, "modelo": modelo, "actor_id": request.user.pk})
    messages.success(request, f"Estación '{estacion}' → {proveedor}.")
    return redirect("los_chalanes:panel")


@require_POST
@requires_role("super_admin")
def reordenar_cadena(request):
    proveedor = request.POST.get("proveedor") or ""
    direccion = request.POST.get("direccion") or "up"  # up | down
    fila = CadenaFallback.objects.filter(proveedor=proveedor).first()
    if not fila:
        return redirect("los_chalanes:panel")
    vecinos = list(CadenaFallback.objects.all().order_by("prioridad"))
    idx = next((i for i, f in enumerate(vecinos) if f.pk == fila.pk), None)
    if idx is None:
        return redirect("los_chalanes:panel")
    swap_idx = idx - 1 if direccion == "up" else idx + 1
    if 0 <= swap_idx < len(vecinos):
        a, b = vecinos[idx], vecinos[swap_idx]
        a.prioridad, b.prioridad = b.prioridad, a.prioridad
        a.save(update_fields=["prioridad"])
        b.save(update_fields=["prioridad"])
        with contextlib.suppress(Exception):
            emitir({"tipo": "chalanes.cadena_actualizada", "actor_id": request.user.pk})
    return redirect("los_chalanes:panel")


@require_POST
@requires_role("super_admin")
def toggle_cadena(request):
    proveedor = request.POST.get("proveedor") or ""
    fila = CadenaFallback.objects.filter(proveedor=proveedor).first()
    if fila:
        fila.activo = not fila.activo
        fila.save(update_fields=["activo"])
        with contextlib.suppress(Exception):
            emitir({"tipo": "chalanes.cadena_actualizada", "actor_id": request.user.pk})
    return redirect("los_chalanes:panel")
