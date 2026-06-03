"""Chalanes (admin) — panel de El Cuadro + La Cadena + Auditoría + Aprendizajes.

Solo super_admin puede modificar; dueño puede ver. Los aprendizajes (S2b.2.1)
viven en la tabla compartida `el_dictado_aprendizaje` y se gestionan desde
aquí: el Taller los consume al construir el prompt del Dictado.
"""

from __future__ import annotations

import contextlib

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ajustes.models.analistas_log import AnalistaLog
from ajustes.models.credencial import Credencial
from chalanes.models import Aprendizaje, CadenaFallback, CuadroChalanes
from chalanes.models.cuadro_chalanes import PROVEEDORES
from lib.analistas.registry import adapter_de
from lib.analistas.stats import resumen_global, tarjetas_chalanes
from lib.dictado_catalogo import COMANDOS_DICTADO, COMANDOS_PROHIBIDOS, REFERENCIAS_ENTRE_ACCIONES
from lib.permisos import es_super_admin, requires_role
from lib.portavoz import emitir

from .forms import AprendizajeForm


@requires_role("super_admin", "dueno")
def panel(request):
    cuadro = CuadroChalanes.objects.all().order_by("estacion")
    cadena = CadenaFallback.objects.all().order_by("prioridad")
    logs = AnalistaLog.objects.all().order_by("-creado_en")[:50]
    return render(request, "los_chalanes/panel.html", {
        "cuadro": cuadro,
        "cadena": cadena,
        "logs": logs,
        "puede_modificar": es_super_admin(request.user),
        "total_aprendizajes": Aprendizaje.objects.count(),
        "aprendizajes_activos_count": Aprendizaje.objects.filter(activo=True).count(),
        "tarjetas": tarjetas_chalanes(dias=30),
        "resumen": resumen_global(dias=30),
        "proveedores_opciones": list(PROVEEDORES),
        "comandos_dictado": COMANDOS_DICTADO,
        "comandos_prohibidos": COMANDOS_PROHIBIDOS,
        "referencias_entre_acciones": REFERENCIAS_ENTRE_ACCIONES,
    })


@require_POST
@requires_role("super_admin", "dueno")
def consultar_saldo_chalan(request, nombre: str):
    """POST /chalanes/<nombre>/saldo — consulta saldo y muestra como flash."""
    adapter = adapter_de(nombre)
    if adapter is None:
        messages.error(request, f"Chalán desconocido: {nombre}")
        return redirect("los_chalanes:panel")
    try:
        saldo = adapter.consultar_saldo()
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Chalán {nombre}: no se pudo consultar saldo ({exc}).")
        return redirect("los_chalanes:panel")
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
    return redirect("los_chalanes:panel")


@require_POST
@requires_role("super_admin")
def probar_chalan(request, nombre: str):
    """POST /chalanes/<nombre>/probar — ping de 1 token y persiste resultado."""
    adapter = adapter_de(nombre)
    if adapter is None:
        messages.error(request, f"Chalán desconocido: {nombre}")
        return redirect("los_chalanes:panel")
    resultado = adapter.probar()
    slot = f"chalan_{nombre}_api_key"
    cred = Credencial.objects.filter(clave=slot).first()
    if cred is not None:
        cred.ultimo_test_en = timezone.now()
        cred.ultimo_test_ok = resultado["ok"]
        cred.ultimo_test_mensaje = (resultado.get("mensaje") or "")[:240]
        cred.save(update_fields=["ultimo_test_en", "ultimo_test_ok", "ultimo_test_mensaje"])
    if resultado["ok"]:
        latencia = resultado.get("latencia_ms") or "?"
        messages.success(request, f"Chalán {nombre}: conexión OK ({latencia} ms).")
    elif resultado.get("estado") == "no_configurada":
        messages.warning(request, f"Chalán {nombre}: sin credencial. Configúrala en Los Ajustes.")
    else:
        messages.error(request, f"Chalán {nombre}: {resultado.get('mensaje', 'error')[:200]}")
    with contextlib.suppress(Exception):
        emitir({"tipo": "chalanes.probado", "proveedor": nombre,
                "ok": resultado["ok"], "latencia_ms": resultado.get("latencia_ms"),
                "actor_id": request.user.pk})
    return redirect("los_chalanes:panel")


@require_POST
@requires_role("super_admin")
def borrar_llave(request, nombre: str):
    """POST /chalanes/<nombre>/borrar-llave — borra credencial del slot."""
    slot = f"chalan_{nombre}_api_key"
    qs = Credencial.objects.filter(clave=slot)
    existia = qs.exists()
    qs.delete()
    if existia:
        messages.success(request, f"Llave del Chalán {nombre} eliminada.")
        with contextlib.suppress(Exception):
            emitir({"tipo": "chalanes.llave_borrada", "proveedor": nombre,
                    "actor_id": request.user.pk})
    return redirect("los_chalanes:panel")


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
    direccion = request.POST.get("direccion") or "up"
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


# ── Aprendizajes (S2b.2.1) ───────────────────────────────────────────


@requires_role("super_admin", "dueno")
def aprendizajes_lista(request):
    filtro = request.GET.get("filtro") or "activos"
    qs = Aprendizaje.objects.all()
    if filtro == "activos":
        qs = qs.filter(activo=True)
    elif filtro == "inactivos":
        qs = qs.filter(activo=False)
    aprendizajes = list(qs.order_by("-creado_en")[:200])
    # Pre-calcula peso_efectivo para la UI.
    for ap in aprendizajes:
        ap.peso_efectivo_calc = round(ap.peso_efectivo(), 2)
        ap.bajo_umbral = ap.peso_efectivo_calc < 0.3
    return render(request, "los_chalanes/aprendizajes_lista.html", {
        "aprendizajes": aprendizajes,
        "filtro": filtro,
        "puede_modificar": es_super_admin(request.user),
        "totales": {
            "todos": Aprendizaje.objects.count(),
            "activos": Aprendizaje.objects.filter(activo=True).count(),
            "inactivos": Aprendizaje.objects.filter(activo=False).count(),
        },
        "breadcrumb_items": [
            {"url": "/chalanes/", "label": "Chalanes"},
            {"label": "Aprendizajes"},
        ],
        "back_url": "/chalanes/",
        "back_label": "Chalanes",
    })


@requires_role("super_admin")
def aprendizaje_nuevo(request):
    if request.method == "POST":
        form = AprendizajeForm(request.POST)
        if form.is_valid():
            ap = form.save(commit=False)
            ap.autor = request.user
            ap.save()
            with contextlib.suppress(Exception):
                emitir({"tipo": "chalanes.aprendizaje_creado",
                        "aprendizaje_id": ap.pk,
                        "frase": ap.frase_o_patron[:80],
                        "actor_id": request.user.pk})
            messages.success(request, "Aprendizaje guardado. El Chalán lo usará en el próximo dictado.")
            return redirect("los_chalanes:aprendizajes-lista")
    else:
        form = AprendizajeForm()
    return render(request, "los_chalanes/aprendizaje_form.html", {
        "form": form, "es_nuevo": True,
    })


@requires_role("super_admin")
def aprendizaje_editar(request, pk: int):
    ap = get_object_or_404(Aprendizaje, pk=pk)
    if request.method == "POST":
        form = AprendizajeForm(request.POST, instance=ap)
        if form.is_valid():
            form.save()
            with contextlib.suppress(Exception):
                emitir({"tipo": "chalanes.aprendizaje_actualizado",
                        "aprendizaje_id": ap.pk, "actor_id": request.user.pk})
            messages.success(request, "Aprendizaje actualizado.")
            return redirect("los_chalanes:aprendizajes-lista")
    else:
        form = AprendizajeForm(instance=ap)
    return render(request, "los_chalanes/aprendizaje_form.html", {
        "form": form, "aprendizaje": ap, "es_nuevo": False,
    })


@requires_role("super_admin", "dueno")
def kpis_pendientes(request):
    """Lista los KPICustom de equipo en estado pendiente_aprobacion."""
    from apps.taller_home.models import KPICustom
    pendientes = list(
        KPICustom.objects.filter(alcance="equipo", estado="pendiente_aprobacion")
        .order_by("creado_en")[:50],
    )
    for k in pendientes:
        # Pre-ejecuta para mostrar el valor al super_admin.
        try:
            from lib.kpi_dsl import ejecutar
            k.valor_preview = ejecutar(k.definicion_json, usuario=request.user)
        except Exception:  # noqa: BLE001
            k.valor_preview = {"valor": "?", "nota": "error", "link": ""}
    return render(request, "los_chalanes/kpis_pendientes.html", {
        "pendientes": pendientes,
        "puede_modificar": es_super_admin(request.user),
    })


@require_POST
@requires_role("super_admin")
def kpi_aprobar(request, pk: int):
    from apps.taller_home.models import KPICustom
    kpi = get_object_or_404(KPICustom, pk=pk, alcance="equipo", estado="pendiente_aprobacion")
    kpi.estado = "activo"
    kpi.aprobado_por = request.user
    kpi.aprobado_en = timezone.now()
    kpi.save(update_fields=["estado", "aprobado_por", "aprobado_en"])
    with contextlib.suppress(Exception):
        emitir({"tipo": "kpi_custom.aprobado", "kpi_id": kpi.pk,
                "actor_id": request.user.pk})
    messages.success(request, f"KPI '{kpi.titulo}' aprobado — visible al equipo.")
    return redirect("los_chalanes:kpis-pendientes")


@require_POST
@requires_role("super_admin")
def kpi_rechazar(request, pk: int):
    from apps.taller_home.models import KPICustom
    kpi = get_object_or_404(KPICustom, pk=pk, alcance="equipo", estado="pendiente_aprobacion")
    motivo = (request.POST.get("motivo") or "")[:300]
    kpi.estado = "rechazado"
    kpi.motivo_rechazo = motivo
    kpi.aprobado_por = request.user
    kpi.aprobado_en = timezone.now()
    kpi.save(update_fields=["estado", "motivo_rechazo", "aprobado_por", "aprobado_en"])
    with contextlib.suppress(Exception):
        emitir({"tipo": "kpi_custom.rechazado", "kpi_id": kpi.pk,
                "motivo": motivo, "actor_id": request.user.pk})
    messages.success(request, f"KPI '{kpi.titulo}' rechazado.")
    return redirect("los_chalanes:kpis-pendientes")


@require_POST
@requires_role("super_admin")
def aprendizaje_toggle(request, pk: int):
    ap = get_object_or_404(Aprendizaje, pk=pk)
    ap.activo = not ap.activo
    if ap.activo:
        ap.desactivado_en = None
        ap.desactivado_por = None
        ap.motivo_desactivacion = ""
    else:
        ap.desactivado_en = timezone.now()
        ap.desactivado_por = request.user
        ap.motivo_desactivacion = (request.POST.get("motivo") or "")[:200]
    ap.save(update_fields=["activo", "desactivado_en", "desactivado_por", "motivo_desactivacion"])
    with contextlib.suppress(Exception):
        emitir({"tipo": "chalanes.aprendizaje_toggled",
                "aprendizaje_id": ap.pk, "activo": ap.activo,
                "actor_id": request.user.pk})
    messages.success(request, f"Aprendizaje {'activado' if ap.activo else 'desactivado'}.")
    return redirect("los_chalanes:aprendizajes-lista")
