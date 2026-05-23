"""Perfil personal de Chalanes — /perfil/chalanes/ (deuda Pre-S2b.1 saldada en Pre-S2b.2).

El usuario ve sus override personales (`ChalanAsignado`) por estación. Si no
tiene fila, el sistema usa el Chalán del Cuadro global. Aquí puede:
- Asignarse un Chalán distinto por estación.
- Borrar el override (vuelve al default del equipo).

Filtros:
- Las estaciones que requieren VISION ocultan Chalanes sin esa capacidad.
- Diseñadores solo ven estaciones "relevantes" — concretamente, NO ocr_recibo
  (que es para Tesorería, donde el diseñador no entra).
"""

from __future__ import annotations

import contextlib

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from chalanes.models import ChalanAsignado, CuadroChalanes
from lib.analistas import registry as _registry
from lib.analistas.capacidades import Capability
from lib.analistas.stats import resumen_global, tarjetas_chalanes
from lib.dictado_catalogo import COMANDOS_DICTADO, COMANDOS_PROHIBIDOS
from lib.portavoz import emitir

ROLES_ADMIN_TALLER = {"super_admin", "dueno"}

# Estaciones ocultas a roles operativos no-admin (Pre-S2b.1 acuerdo).
ESTACIONES_OCULTAS_DISENADOR = {"ocr_recibo", "dictado_gasto"}


@login_required
def panel(request):
    user = request.user
    rol = getattr(user, "rol", None)

    # Estaciones disponibles.
    cuadro_qs = CuadroChalanes.objects.all().order_by("estacion")
    if rol == "disenador":
        cuadro_qs = cuadro_qs.exclude(estacion__in=ESTACIONES_OCULTAS_DISENADOR)

    asignados = {
        a.estacion: a for a in ChalanAsignado.objects.filter(usuario=user)
    }

    # Lista de Chalanes disponibles globalmente con su capability set.
    chalanes_todos = [
        {"nombre": nombre, "apodo": _registry.apodo(nombre),
         "capacidades": set(getattr(adapter_cls, "capacidades", set()) or set())}
        for nombre, adapter_cls in _registry._FACTORIES.items()
    ]

    filas = []
    for fila_cuadro in cuadro_qs:
        # Chalanes válidos para esta estación: filtro por VISION si la requiere.
        if fila_cuadro.requiere_vision:
            elegibles = [c for c in chalanes_todos if Capability.VISION in c["capacidades"]]
        else:
            elegibles = list(chalanes_todos)
        override = asignados.get(fila_cuadro.estacion)
        filas.append({
            "estacion": fila_cuadro.estacion,
            "descripcion": fila_cuadro.descripcion,
            "requiere_vision": fila_cuadro.requiere_vision,
            "default_equipo": _registry.apodo(fila_cuadro.proveedor),
            "default_proveedor": fila_cuadro.proveedor,
            "elegibles": elegibles,
            "override_proveedor": override.proveedor if override else "",
        })

    ctx = {
        "filas": filas,
        "comandos_dictado": COMANDOS_DICTADO,
        "comandos_prohibidos": COMANDOS_PROHIBIDOS,
    }
    if rol in ROLES_ADMIN_TALLER:
        # Dashboard reducido para admins (mismo dato que /chalanes/ en Gerencia,
        # sin acciones de admin — solo lectura). Defensivo: si la query falla
        # por algún motivo, omite la sección.
        try:
            ctx["tarjetas_chalanes"] = tarjetas_chalanes(dias=30)
            ctx["resumen_chalanes"] = resumen_global(dias=30)
        except Exception:  # noqa: BLE001
            ctx["tarjetas_chalanes"] = []
            ctx["resumen_chalanes"] = None
    return render(request, "perfil_chalanes/panel.html", ctx)


@require_POST
@login_required
def guardar(request):
    user = request.user
    estacion = request.POST.get("estacion") or ""
    proveedor = (request.POST.get("proveedor") or "").strip()

    cuadro = CuadroChalanes.objects.filter(estacion=estacion).first()
    if not cuadro:
        messages.error(request, "Estación desconocida.")
        return redirect("perfil-chalanes")

    # Validación VISION.
    if cuadro.requiere_vision and proveedor:
        adapter = _registry._FACTORIES.get(proveedor)
        if adapter is not None and Capability.VISION not in (getattr(adapter, "capacidades", set()) or set()):
            messages.error(request, f"Esa estación requiere visión y {proveedor} no la soporta.")
            return redirect("perfil-chalanes")

    if not proveedor:
        # Borrar override → vuelve al default del equipo.
        ChalanAsignado.objects.filter(usuario=user, estacion=estacion).delete()
        messages.success(request, f"Estación '{estacion}' volvió al Chalán predeterminado del equipo.")
    else:
        ChalanAsignado.objects.update_or_create(
            usuario=user, estacion=estacion,
            defaults={"proveedor": proveedor, "modelo": "", "motivo": ""},
        )
        messages.success(request, f"Estación '{estacion}' → {_registry.apodo(proveedor)}.")

    with contextlib.suppress(Exception):
        emitir({
            "tipo": "chalanes.asignacion_personal_actualizada",
            "usuario_id": user.pk, "estacion": estacion,
            "proveedor": proveedor or None,
        })
    return redirect("perfil-chalanes")
