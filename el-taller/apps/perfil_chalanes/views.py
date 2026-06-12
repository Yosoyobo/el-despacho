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
from lib.analistas.stats import (
    estadisticas_por_estacion,
    kpis_consumo,
    resumen_global,
    tarjetas_chalanes,
    usuarios_top,
)
from lib.dictado_catalogo import COMANDOS_DICTADO, COMANDOS_PROHIBIDOS, REFERENCIAS_ENTRE_ACCIONES
from lib.permisos import roles_efectivos, tiene_rol
from lib.portavoz import emitir

ROLES_ADMIN_TALLER = {"super_admin", "dueno"}

# Estaciones ocultas a roles operativos no-admin (Pre-S2b.1 acuerdo).
ESTACIONES_OCULTAS_DISENADOR = {"ocr_recibo", "dictado_gasto"}


@login_required
def panel(request):
    user = request.user
    # V6 Bloque 10: roles efectivos (rol primario + roles personalizados).
    roles = roles_efectivos(user)

    # Estaciones disponibles.
    cuadro_qs = CuadroChalanes.objects.all().order_by("estacion")
    if "disenador" in roles and not (roles & {"super_admin", "dueno", "contador"}):
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
        "referencias_entre_acciones": REFERENCIAS_ENTRE_ACCIONES,
    }
    # S-Chalanes-Consumo: la analítica de consumo (30 días) es SOLO para
    # super_admin en el Taller (decisión Oscar). Defensivo: si la query falla,
    # omite la sección sin tumbar el panel.
    # V6 Bloque 10: tiene_rol reconoce rol primario + roles personalizados.
    es_super = tiene_rol(user, "super_admin")
    ctx["es_super_admin_taller"] = es_super
    if es_super:
        try:
            ctx["tarjetas_chalanes"] = tarjetas_chalanes(dias=30)
            ctx["resumen_chalanes"] = resumen_global(dias=30)
            ctx["kpis_consumo"] = kpis_consumo(dias=30)
            ctx["por_estacion"] = estadisticas_por_estacion(dias=30)
            ctx["usuarios_top"] = usuarios_top(dias=30, limit=8)
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


@require_POST
@login_required
def guardar_voz(request):
    """POST /perfil/chalanes/voz — guarda la voz/estilo personal del usuario.

    Capa aditiva sobre la voz institucional. Solo afecta tono en flujos
    conversacionales (Dictado, chat). Vacío = sin personalización."""
    from lib.sanear import sanear_contexto

    crudo = (request.POST.get("voz_chalan") or "").strip()
    # Saneamos y acotamos antes de persistir (defensa en profundidad — voz.py
    # vuelve a sanear al inyectar).
    limpio = sanear_contexto(crudo, max_len=4000) if crudo else ""
    request.user.voz_chalan = limpio
    request.user.save(update_fields=["voz_chalan"])
    with contextlib.suppress(Exception):
        emitir({
            "tipo": "chalan.voz_personal_actualizada",
            "usuario_id": request.user.pk,
            "vacia": not bool(limpio),
        })
    if limpio:
        messages.success(request, "Tu estilo personal con El Chalán quedó guardado.")
    else:
        messages.success(request, "Tu estilo personal quedó vacío (vuelves al tono del equipo).")
    return redirect("perfil-chalanes")


@require_POST
@login_required
def consultar_saldo(request, nombre: str):
    """POST /perfil/chalanes/<nombre>/saldo — solo super_admin/dueno.

    Misma lógica que en Gerencia, pero accesible desde el panel del Taller.
    """
    # V6 Bloque 10: tiene_rol reconoce rol primario + roles personalizados.
    if not tiene_rol(request.user, "super_admin", "dueno"):
        messages.error(request, "Sólo super_admin y dueño pueden consultar saldo.")
        return redirect("perfil-chalanes")
    adapter = _registry.adapter_de(nombre)
    if adapter is None:
        messages.error(request, f"Chalán desconocido: {nombre}")
        return redirect("perfil-chalanes")
    try:
        saldo = adapter.consultar_saldo()
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Chalán {nombre}: no se pudo consultar saldo ({exc}).")
        return redirect("perfil-chalanes")
    etiqueta = saldo.get("etiqueta") or "—"
    mensaje = saldo.get("mensaje") or ""
    url = saldo.get("fuente_url") or ""
    if saldo.get("soportado") and saldo.get("disponible") is not None:
        messages.success(request, f"Saldo de {nombre}: {etiqueta} · {mensaje}")
    elif saldo.get("soportado"):
        messages.info(request, f"Saldo de {nombre}: {etiqueta}. {mensaje} {url}".strip())
    else:
        messages.info(request, f"Saldo de {nombre}: este proveedor no expone saldo vía API. Revisa: {url}")
    with contextlib.suppress(Exception):
        emitir({"tipo": "chalanes.saldo_consultado", "proveedor": nombre,
                "soportado": saldo.get("soportado"), "etiqueta": etiqueta,
                "actor_id": request.user.pk})
    return redirect("perfil-chalanes")
