"""Vistas de La Tesorería (S2b.3 V1).

Pipeline OCR de recibos (DOC_06 §6) y export a Google Sheets (§8.2.4)
quedan diferidos a S2b.3b — requieren wrappers de Google Drive/Sheets
funcionales. Forms, CRUD manual, CxC/CxP, reportes y exports CSV
están completos."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import puede_ver_finanzas
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from . import exports, services
from .forms import AnularForm, EgresoForm, IngresoForm
from .models import Egreso, Ingreso
from .push_handlers import notificar_reembolso_pendiente

# ── Helpers ────────────────────────────────────────────────────────────────


def _gate(request):
    if not puede_ver_finanzas(request.user):
        return HttpResponseForbidden("Sin acceso a La Tesorería.")
    return None


def _emitir(tipo: str, request, payload: dict) -> None:
    emitir(EventoPortavoz(
        tipo=tipo, actor_id=request.user.pk, actor_email=request.user.email,
        payload=payload,
    ))


# ── Landing ────────────────────────────────────────────────────────────────


@login_required
def landing(request):
    if (r := _gate(request)) is not None:
        return r
    kpis = services.kpis_landing(request.user)
    kpis_fmt = {
        "ingresos_mes_fmt": f"${kpis['ingresos_mes']:,.2f}",
        "egresos_mes_fmt": f"${kpis['egresos_mes']:,.2f}",
        "utilidad_mes_fmt": f"${kpis['utilidad_mes']:,.2f}",
        "cxp_total_fmt": f"${kpis['cxp_total']:,.2f}",
        **kpis,
    }
    return render(request, "tesoreria/landing.html", {
        "kpis": kpis_fmt,
        "charts": services.charts_landing(),
        "ultimos_ingresos": Ingreso.vigentes.all()[:5],
        "ultimos_egresos": Egreso.vigentes.all()[:5],
    })


# ── Ingresos ───────────────────────────────────────────────────────────────


@login_required
def ingresos_lista(request):
    if (r := _gate(request)) is not None:
        return r
    qs = Ingreso.objects.all() if request.GET.get("anulados") == "1" else Ingreso.vigentes.all()
    qs = qs.select_related("cliente", "proyecto", "creado_por")
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(descripcion__icontains=q)
    return render(request, "tesoreria/ingresos_lista.html", {
        "ingresos": qs[:200],
        "q": q,
        "incluye_anulados": request.GET.get("anulados") == "1",
    })


@login_required
def ingreso_detalle(request, pk):
    if (r := _gate(request)) is not None:
        return r
    ingreso = get_object_or_404(Ingreso, pk=pk)
    return render(request, "tesoreria/ingreso_detalle.html", {"ingreso": ingreso})


@login_required
def ingreso_nuevo(request):
    if (r := _gate(request)) is not None:
        return r
    if request.method == "POST":
        form = IngresoForm(request.POST)
        if form.is_valid():
            ingreso = form.save(commit=False)
            ingreso.creado_por = request.user
            ingreso.save()
            _emitir("tesoreria.ingreso_registrado", request, {
                "ingreso_id": ingreso.pk, "monto": str(ingreso.monto),
                "cliente_id": ingreso.cliente_id, "proyecto_id": ingreso.proyecto_id,
                "origen": "manual",
            })
            messages.success(request, f"Ingreso {ingreso.codigo} registrado.")
            return redirect("tesoreria:ingreso-detalle", pk=ingreso.pk)
    else:
        form = IngresoForm()
    return render(request, "tesoreria/ingreso_form.html", {"form": form, "modo": "nuevo"})


@login_required
def ingreso_editar(request, pk):
    if (r := _gate(request)) is not None:
        return r
    ingreso = get_object_or_404(Ingreso, pk=pk)
    if ingreso.anulado:
        messages.error(request, "Un ingreso anulado no se edita.")
        return redirect("tesoreria:ingreso-detalle", pk=ingreso.pk)
    if request.method == "POST":
        form = IngresoForm(request.POST, instance=ingreso)
        if form.is_valid():
            form.save()
            messages.success(request, "Ingreso actualizado.")
            return redirect("tesoreria:ingreso-detalle", pk=ingreso.pk)
    else:
        form = IngresoForm(instance=ingreso)
    return render(request, "tesoreria/ingreso_form.html",
                  {"form": form, "modo": "editar", "ingreso": ingreso})


@login_required
def ingreso_anular(request, pk):
    if (r := _gate(request)) is not None:
        return r
    ingreso = get_object_or_404(Ingreso, pk=pk)
    if ingreso.anulado:
        return redirect("tesoreria:ingreso-detalle", pk=ingreso.pk)
    if request.method == "POST":
        form = AnularForm(request.POST)
        if form.is_valid():
            services.anular_ingreso(ingreso, request.user, form.cleaned_data["motivo"])
            _emitir("tesoreria.ingreso_anulado", request, {
                "ingreso_id": ingreso.pk,
                "motivo": ingreso.motivo_anulacion,
                "anulado_por_id": request.user.pk,
            })
            messages.success(request, f"Ingreso {ingreso.codigo} anulado.")
            return redirect("tesoreria:ingreso-detalle", pk=ingreso.pk)
    else:
        form = AnularForm()
    return render(request, "tesoreria/anular.html",
                  {"form": form, "objeto": ingreso, "tipo": "ingreso"})


# ── Egresos ────────────────────────────────────────────────────────────────


@login_required
def egresos_lista(request):
    if (r := _gate(request)) is not None:
        return r
    qs = Egreso.objects.all() if request.GET.get("anulados") == "1" else Egreso.vigentes.all()
    qs = qs.select_related("centro_de_costo", "proyecto", "pagado_por", "creado_por")
    q = (request.GET.get("q") or "").strip()
    centro = request.GET.get("centro") or ""
    estado = request.GET.get("estado_pago") or ""
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(descripcion__icontains=q) | Q(proveedor_nombre__icontains=q))
    if centro:
        qs = qs.filter(centro_de_costo__slug=centro)
    if estado:
        qs = qs.filter(estado_pago=estado)
    from .models import CentroDeCosto
    return render(request, "tesoreria/egresos_lista.html", {
        "egresos": qs[:200],
        "q": q, "centro": centro, "estado_pago": estado,
        "centros": CentroDeCosto.objects.filter(activo=True),
        "incluye_anulados": request.GET.get("anulados") == "1",
    })


@login_required
def egreso_detalle(request, pk):
    if (r := _gate(request)) is not None:
        return r
    egreso = get_object_or_404(Egreso, pk=pk)
    return render(request, "tesoreria/egreso_detalle.html", {"egreso": egreso})


@login_required
def egreso_nuevo(request):
    if (r := _gate(request)) is not None:
        return r
    if request.method == "POST":
        form = EgresoForm(request.POST)
        if form.is_valid():
            egreso = form.save(commit=False)
            egreso.creado_por = request.user
            if not egreso.pagado_por:
                egreso.pagado_por = request.user
            egreso.save()
            _emitir("tesoreria.egreso_registrado", request, {
                "egreso_id": egreso.pk, "monto": str(egreso.monto),
                "centro_de_costo_id": egreso.centro_de_costo_id,
                "proyecto_id": egreso.proyecto_id, "origen": egreso.origen,
            })
            if egreso.estado_pago == "por_reembolsar":
                _emitir("tesoreria.reembolso_pendiente", request, {
                    "egreso_id": egreso.pk,
                    "pagado_por_id": egreso.pagado_por_id,
                    "monto": str(egreso.monto),
                })
                notificar_reembolso_pendiente(egreso, request.user)
            messages.success(request, f"Egreso {egreso.codigo} registrado.")
            return redirect("tesoreria:egreso-detalle", pk=egreso.pk)
    else:
        form = EgresoForm()
    return render(request, "tesoreria/egreso_form.html", {"form": form, "modo": "nuevo"})


@login_required
def egreso_editar(request, pk):
    if (r := _gate(request)) is not None:
        return r
    egreso = get_object_or_404(Egreso, pk=pk)
    if egreso.anulado:
        messages.error(request, "Un egreso anulado no se edita.")
        return redirect("tesoreria:egreso-detalle", pk=egreso.pk)
    estado_previo = egreso.estado_pago
    if request.method == "POST":
        form = EgresoForm(request.POST, instance=egreso)
        if form.is_valid():
            form.save()
            if (
                form.cleaned_data["estado_pago"] == "por_reembolsar"
                and estado_previo != "por_reembolsar"
            ):
                _emitir("tesoreria.reembolso_pendiente", request, {
                    "egreso_id": egreso.pk,
                    "pagado_por_id": egreso.pagado_por_id,
                    "monto": str(egreso.monto),
                })
                notificar_reembolso_pendiente(egreso, request.user)
            messages.success(request, "Egreso actualizado.")
            return redirect("tesoreria:egreso-detalle", pk=egreso.pk)
    else:
        form = EgresoForm(instance=egreso)
    return render(request, "tesoreria/egreso_form.html",
                  {"form": form, "modo": "editar", "egreso": egreso})


@login_required
def egreso_anular(request, pk):
    if (r := _gate(request)) is not None:
        return r
    egreso = get_object_or_404(Egreso, pk=pk)
    if egreso.anulado:
        return redirect("tesoreria:egreso-detalle", pk=egreso.pk)
    if request.method == "POST":
        form = AnularForm(request.POST)
        if form.is_valid():
            services.anular_egreso(egreso, request.user, form.cleaned_data["motivo"])
            _emitir("tesoreria.egreso_anulado", request, {
                "egreso_id": egreso.pk,
                "motivo": egreso.motivo_anulacion,
                "anulado_por_id": request.user.pk,
            })
            messages.success(request, f"Egreso {egreso.codigo} anulado.")
            return redirect("tesoreria:egreso-detalle", pk=egreso.pk)
    else:
        form = AnularForm()
    return render(request, "tesoreria/anular.html",
                  {"form": form, "objeto": egreso, "tipo": "egreso"})


# ── Cuentas por cobrar / pagar ─────────────────────────────────────────────


@login_required
def por_cobrar(request):
    if (r := _gate(request)) is not None:
        return r
    proyectos_saldos = services.cxc_proyectos()
    total = sum(s for _, s in proyectos_saldos)
    return render(request, "tesoreria/por_cobrar.html", {
        "proyectos_saldos": proyectos_saldos, "total": total,
    })


@login_required
def por_pagar(request):
    if (r := _gate(request)) is not None:
        return r
    estado = request.GET.get("estado_pago") or ""
    qs = services.cuentas_por_pagar_qs().select_related("pagado_por")
    if estado:
        qs = qs.filter(estado_pago=estado)
    qs = qs.order_by("fecha")
    total = sum((e.monto for e in qs), 0)
    return render(request, "tesoreria/por_pagar.html", {
        "egresos": qs, "estado_pago": estado, "total": total,
        "reembolsos": services.reembolsos_pendientes(),
    })


# ── Reportes ───────────────────────────────────────────────────────────────


@login_required
def reportes(request):
    if (r := _gate(request)) is not None:
        return r
    from datetime import date as _d
    hoy = _d.today()
    try:
        anio = int(request.GET.get("anio") or hoy.year)
        mes = int(request.GET.get("mes") or hoy.month)
    except ValueError:
        anio, mes = hoy.year, hoy.month
    if not 1 <= mes <= 12:
        mes = hoy.month
    return render(request, "tesoreria/reportes.html", {
        "reporte": services.reporte_mes(anio, mes),
        "anio": anio, "mes": mes,
    })


# ── Exports CSV ────────────────────────────────────────────────────────────


@login_required
def exportar(request, vista):
    if (r := _gate(request)) is not None:
        return r
    if vista not in exports.VISTAS:
        return HttpResponseNotAllowed(["GET"])
    response, num_filas = exports.responder_csv(vista, request.GET.dict())
    _emitir("tesoreria.exportado", request, {
        "vista": vista, "formato": "csv", "filas": num_filas,
        "filtros": dict(request.GET),
    })
    return response
