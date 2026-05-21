"""Views de La Contaduría."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from lib.permisos import (
    puede_anular_contaduria,
    puede_capturar_contaduria,
    puede_reportes_contaduria,
    puede_ver_contaduria,
)

from . import exports, reportes, services, wizards
from .forms import AnularForm, AsientoForm, PartidaFormSet
from .models import Asiento, CuentaContable, Partida


def _parsear_fecha(valor: str) -> date | None:
    valor = (valor or "").strip()
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return None

CERO = Decimal("0.00")
ORDEN_ASIENTOS = {"codigo", "fecha", "origen", "descripcion", "creado_en"}


def _gate_ver(request):
    if not puede_ver_contaduria(request.user):
        return HttpResponseForbidden("Sin acceso a La Contaduría.")
    return None


def _es_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


@login_required
def landing(request):
    if (r := _gate_ver(request)) is not None:
        return r
    ultimos = Asiento.vigentes.order_by("-fecha", "-creado_en")[:8]
    return render(request, "contaduria/landing.html", {
        "kpis": services.kpis_landing(),
        "ultimos": ultimos,
        "puede_capturar": puede_capturar_contaduria(request.user),
    })


@login_required
def cuentas(request):
    if (r := _gate_ver(request)) is not None:
        return r
    q = (request.GET.get("q") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    qs = CuentaContable.objects.all()
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(nombre__icontains=q))
    if tipo in {"activo", "pasivo", "capital", "ingreso", "egreso"}:
        qs = qs.filter(tipo=tipo)
    return render(request, "contaduria/cuentas.html", {
        "cuentas": qs.order_by("codigo"),
        "q": q,
        "tipo_filtro": tipo,
    })


@login_required
def asientos(request):
    if (r := _gate_ver(request)) is not None:
        return r
    q = (request.GET.get("q") or "").strip()
    origen = (request.GET.get("origen") or "").strip()
    incluir_anulados = request.GET.get("anulados") == "1"
    qs = Asiento.objects.select_related("creado_por")
    qs = qs if incluir_anulados else qs.filter(anulado=False)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    if origen:
        qs = qs.filter(origen=origen)

    orden = (request.GET.get("orden") or "-fecha").strip()
    base = orden.lstrip("-")
    if base not in ORDEN_ASIENTOS:
        orden = "-fecha"
    qs = qs.order_by(orden, "-pk")

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    qs_filtros = []
    if q:
        qs_filtros.append(f"q={q}")
    if origen:
        qs_filtros.append(f"origen={origen}")
    if incluir_anulados:
        qs_filtros.append("anulados=1")

    return render(request, "contaduria/asientos.html", {
        "page_obj": page_obj,
        "asientos": page_obj.object_list,
        "q": q,
        "origen_filtro": origen,
        "incluir_anulados": incluir_anulados,
        "orden_actual": orden,
        "querystring_base": "&".join(qs_filtros),
        "querystring_paginacion": "&".join(qs_filtros + ([f"orden={orden}"] if orden != "-fecha" else [])),
        "cabeceras": [
            {"label": "Código", "sort_key": "codigo"},
            {"label": "Fecha", "sort_key": "fecha"},
            {"label": "Descripción", "sort_key": "descripcion"},
            {"label": "Origen", "sort_key": "origen"},
            {"label": "Total", "align": "right"},
            {"label": "", "align": "right"},
        ],
        "puede_capturar": puede_capturar_contaduria(request.user),
    })


@login_required
def asiento_detalle(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    asiento = get_object_or_404(
        Asiento.objects.select_related("creado_por", "anulado_por"), pk=pk
    )
    partidas = asiento.partidas.select_related("cuenta").all()
    totales = partidas.aggregate(c=Sum("cargo"), a=Sum("abono"))
    return render(request, "contaduria/asiento_detalle.html", {
        "asiento": asiento,
        "partidas": partidas,
        "total_cargos": totales["c"] or CERO,
        "total_abonos": totales["a"] or CERO,
        "puede_anular": puede_anular_contaduria(request.user) and not asiento.anulado,
    })


@login_required
def asiento_nuevo(request):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_capturar_contaduria(request.user):
        return HttpResponseForbidden("Sin permiso para capturar asientos.")

    if request.method == "POST":
        form = AsientoForm(request.POST)
        formset = PartidaFormSet(request.POST, instance=Asiento())
        if form.is_valid() and formset.is_valid():
            partidas = []
            for f in formset.forms:
                if f.cleaned_data.get("DELETE"):
                    continue
                if f.cleaned_data.get("_vacia"):
                    continue
                if not f.cleaned_data.get("cuenta"):
                    continue
                partidas.append({
                    "cuenta": f.cleaned_data["cuenta"],
                    "cargo": f.cleaned_data.get("cargo") or CERO,
                    "abono": f.cleaned_data.get("abono") or CERO,
                    "descripcion": f.cleaned_data.get("descripcion", ""),
                    "orden": f.cleaned_data.get("orden", 0),
                })
            try:
                asiento = services.crear_asiento(
                    descripcion=form.cleaned_data["descripcion"],
                    fecha=form.cleaned_data.get("fecha"),
                    origen="manual",
                    referencia_externa=form.cleaned_data.get("referencia_externa", ""),
                    partidas=partidas,
                    creado_por=request.user,
                )
            except services.AsientoInvalido as e:
                messages.error(request, str(e))
                return render(request, "contaduria/asiento_form.html", {
                    "form": form, "formset": formset, "cuentas": CuentaContable.activas.all(),
                })
            messages.success(request, f"Asiento {asiento.codigo} creado.")
            return redirect("contaduria:asiento-detalle", pk=asiento.pk)
        return render(request, "contaduria/asiento_form.html", {
            "form": form, "formset": formset, "cuentas": CuentaContable.activas.all(),
        })

    form = AsientoForm()
    formset = PartidaFormSet(instance=Asiento())
    return render(request, "contaduria/asiento_form.html", {
        "form": form, "formset": formset, "cuentas": CuentaContable.activas.all(),
    })


@login_required
def asiento_anular(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    asiento = get_object_or_404(Asiento, pk=pk)
    if not puede_anular_contaduria(request.user):
        return HttpResponseForbidden("Sin permiso para anular asientos.")
    if asiento.anulado:
        messages.error(request, "El asiento ya estaba anulado.")
        return redirect("contaduria:asiento-detalle", pk=asiento.pk)

    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = AnularForm(request.POST)
        if form.is_valid():
            try:
                services.anular_asiento(asiento, actor=request.user, motivo=form.cleaned_data["motivo"])
                messages.success(request, f"Asiento {asiento.codigo} anulado.")
                destino = reverse("contaduria:asiento-detalle", args=[asiento.pk])
                if es_htmx:
                    return HttpResponse(status=204, headers={"HX-Redirect": destino})
                return redirect(destino)
            except services.AsientoInvalido as e:
                messages.error(request, str(e))
        return render(request, "contaduria/_modal_anular.html", {"asiento": asiento, "form": form})
    return render(request, "contaduria/_modal_anular.html", {"asiento": asiento, "form": AnularForm()})


@login_required
def libro_mayor(request, cuenta_pk):
    if (r := _gate_ver(request)) is not None:
        return r
    cuenta = get_object_or_404(CuentaContable, pk=cuenta_pk)
    qs = Partida.objects.filter(cuenta=cuenta, asiento__anulado=False).select_related("asiento").order_by(
        "asiento__fecha", "asiento__creado_en", "pk"
    )
    # Computar saldo acumulado en Python (más simple que window function por compatibilidad SQLite tests)
    movs = []
    saldo = CERO
    for p in qs:
        if cuenta.naturaleza == "deudora":
            saldo += p.cargo - p.abono
        else:
            saldo += p.abono - p.cargo
        movs.append({
            "partida": p,
            "saldo_acumulado": saldo.quantize(Decimal("0.01")),
        })
    return render(request, "contaduria/libro_mayor.html", {
        "cuenta": cuenta,
        "movimientos": movs,
        "saldo_final": services.saldo_cuenta(cuenta),
    })


@login_required
def balance(request):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_reportes_contaduria(request.user):
        return HttpResponseForbidden("Sin permiso para ver reportes.")
    filas = services.balance_de_comprobacion()
    total_c = sum((f["cargos"] for f in filas), CERO)
    total_a = sum((f["abonos"] for f in filas), CERO)
    return render(request, "contaduria/balance.html", {
        "filas": filas,
        "total_cargos": total_c.quantize(Decimal("0.01")),
        "total_abonos": total_a.quantize(Decimal("0.01")),
    })


# ── Estados financieros (V2) ────────────────────────────────────────────

@login_required
def estado_resultados(request):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_reportes_contaduria(request.user):
        return HttpResponseForbidden("Sin permiso para ver reportes.")
    hoy = date.today()
    desde = _parsear_fecha(request.GET.get("desde", "")) or hoy.replace(day=1)
    hasta = _parsear_fecha(request.GET.get("hasta", "")) or hoy
    if desde > hasta:
        desde, hasta = hasta, desde
    pl = reportes.estado_resultados(desde=desde, hasta=hasta)
    return render(request, "contaduria/estado_resultados.html", {
        "pl": pl,
        "desde": desde,
        "hasta": hasta,
    })


@login_required
def balance_general(request):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_reportes_contaduria(request.user):
        return HttpResponseForbidden("Sin permiso para ver reportes.")
    hasta = _parsear_fecha(request.GET.get("hasta", "")) or date.today()
    bg = reportes.balance_general(hasta=hasta)
    return render(request, "contaduria/balance_general.html", {
        "bg": bg,
        "hasta": hasta,
    })


# ── Export al contador externo ─────────────────────────────────────────

@login_required
def export(request):
    """Form HTML para configurar el export. POST/GET con `descargar=1`
    devuelve el CSV directamente."""
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_reportes_contaduria(request.user):
        return HttpResponseForbidden("Sin permiso para exportar.")

    if request.GET.get("descargar") == "1":
        formato = (request.GET.get("formato") or "polizas").strip()
        if formato not in exports.FORMATOS:
            messages.error(request, f"Formato desconocido: {formato}.")
            return redirect("contaduria:export")
        params = {
            "desde": request.GET.get("desde", ""),
            "hasta": request.GET.get("hasta", ""),
            "origen": request.GET.get("origen", ""),
            "incluir_anulados": request.GET.get("incluir_anulados", ""),
            "incluir_inactivas": request.GET.get("incluir_inactivas", ""),
        }
        return exports.responder_csv(formato, params, actor=request.user)

    hoy = date.today()
    return render(request, "contaduria/export.html", {
        "default_desde": hoy.replace(day=1).isoformat(),
        "default_hasta": hoy.isoformat(),
        "formatos": exports.FORMATOS,
    })


# ── Wizard "+ Nuevo movimiento" (dummy-proof) ──────────────────────────

@login_required
def movimiento_nuevo(request):
    """Pantalla 1: usuario elige Traspaso o Ajuste."""
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_capturar_contaduria(request.user):
        return HttpResponseForbidden("Sin permiso para capturar movimientos.")
    return render(request, "contaduria/movimiento_nuevo.html", {})


@login_required
def movimiento_traspaso(request):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_capturar_contaduria(request.user):
        return HttpResponseForbidden("Sin permiso para capturar movimientos.")

    cuentas = wizards.cuentas_traspasables()
    default_fecha = date.today().isoformat()
    if request.method == "POST":
        try:
            origen = cuentas.get(pk=request.POST.get("cuenta_origen") or 0)
        except CuentaContable.DoesNotExist:
            messages.error(request, "Cuenta de origen inválida.")
            return render(request, "contaduria/movimiento_traspaso_form.html", {
                "cuentas": cuentas, "valores": request.POST, "default_fecha": default_fecha,
            })
        try:
            destino = cuentas.get(pk=request.POST.get("cuenta_destino") or 0)
        except CuentaContable.DoesNotExist:
            messages.error(request, "Cuenta de destino inválida.")
            return render(request, "contaduria/movimiento_traspaso_form.html", {
                "cuentas": cuentas, "valores": request.POST, "default_fecha": default_fecha,
            })
        try:
            monto = Decimal(str(request.POST.get("monto") or "0"))
        except Exception:
            messages.error(request, "El monto no es un número válido.")
            return render(request, "contaduria/movimiento_traspaso_form.html", {
                "cuentas": cuentas, "valores": request.POST, "default_fecha": default_fecha,
            })
        fecha_str = (request.POST.get("fecha") or "").strip()
        fecha = _parsear_fecha(fecha_str) or date.today()
        descripcion = (request.POST.get("descripcion") or "").strip()
        if not descripcion:
            messages.error(request, "Describe para qué fue este traspaso.")
            return render(request, "contaduria/movimiento_traspaso_form.html", {
                "cuentas": cuentas, "valores": request.POST, "default_fecha": default_fecha,
            })
        try:
            asiento = wizards.registrar_traspaso(
                cuenta_origen=origen,
                cuenta_destino=destino,
                monto=monto,
                descripcion=descripcion,
                fecha=fecha,
                creado_por=request.user,
            )
        except services.AsientoInvalido as e:
            messages.error(request, str(e))
            return render(request, "contaduria/movimiento_traspaso_form.html", {
                "cuentas": cuentas, "valores": request.POST, "default_fecha": default_fecha,
            })
        messages.success(request, f"Movimiento registrado: {asiento.codigo}")
        return redirect("contaduria:asiento-detalle", pk=asiento.pk)

    # GET: permitir pre-seleccionar origen/destino via query string
    # (?origen=stripe_saldo&destino=banco). Atajo Stripe-payout en
    # /tesoreria/landing/.
    valores_iniciales = {}
    slot_origen = (request.GET.get("origen") or "").strip()
    slot_destino = (request.GET.get("destino") or "").strip()
    if slot_origen:
        c = cuentas.filter(slot=slot_origen).first()
        if c:
            valores_iniciales["cuenta_origen"] = str(c.pk)
    if slot_destino:
        c = cuentas.filter(slot=slot_destino).first()
        if c:
            valores_iniciales["cuenta_destino"] = str(c.pk)
    if request.GET.get("descripcion"):
        valores_iniciales["descripcion"] = request.GET["descripcion"]

    return render(request, "contaduria/movimiento_traspaso_form.html", {
        "cuentas": cuentas, "valores": valores_iniciales,
        "default_fecha": date.today().isoformat(),
    })


@login_required
def movimiento_ajuste(request):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_capturar_contaduria(request.user):
        return HttpResponseForbidden("Sin permiso para capturar movimientos.")

    cuentas = wizards.cuentas_ajustables()
    default_fecha = date.today().isoformat()
    if request.method == "POST":
        try:
            cuenta = cuentas.get(pk=request.POST.get("cuenta") or 0)
        except CuentaContable.DoesNotExist:
            messages.error(request, "Cuenta inválida.")
            return render(request, "contaduria/movimiento_ajuste_form.html", {
                "cuentas": cuentas, "valores": request.POST, "default_fecha": default_fecha,
            })
        direccion = (request.POST.get("direccion") or "").strip()
        try:
            monto = Decimal(str(request.POST.get("monto") or "0"))
        except Exception:
            messages.error(request, "El monto no es un número válido.")
            return render(request, "contaduria/movimiento_ajuste_form.html", {
                "cuentas": cuentas, "valores": request.POST, "default_fecha": default_fecha,
            })
        fecha_str = (request.POST.get("fecha") or "").strip()
        fecha = _parsear_fecha(fecha_str) or date.today()
        motivo = (request.POST.get("motivo") or "").strip()
        if not motivo:
            messages.error(request, "Explica por qué este ajuste.")
            return render(request, "contaduria/movimiento_ajuste_form.html", {
                "cuentas": cuentas, "valores": request.POST, "default_fecha": default_fecha,
            })
        try:
            asiento = wizards.registrar_ajuste(
                cuenta_objetivo=cuenta,
                direccion=direccion,
                monto=monto,
                motivo=motivo,
                fecha=fecha,
                creado_por=request.user,
            )
        except services.AsientoInvalido as e:
            messages.error(request, str(e))
            return render(request, "contaduria/movimiento_ajuste_form.html", {
                "cuentas": cuentas, "valores": request.POST, "default_fecha": default_fecha,
            })
        messages.success(request, f"Movimiento registrado: {asiento.codigo}")
        return redirect("contaduria:asiento-detalle", pk=asiento.pk)

    return render(request, "contaduria/movimiento_ajuste_form.html", {
        "cuentas": cuentas, "valores": {}, "default_fecha": date.today().isoformat(),
    })
