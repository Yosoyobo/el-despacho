"""Vistas de Tesorería (S2b.3 V1).

Pipeline OCR de recibos (DOC_06 §6) y export a Google Sheets (§8.2.4)
quedan diferidos a S2b.3b — requieren wrappers de Google Drive/Sheets
funcionales. Forms, CRUD manual, CxC/CxP, reportes y exports CSV
están completos."""

from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html

from lib.permisos import puede_ver_finanzas
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from . import exports, services
from .forms import AnularForm, EgresoForm, IngresoForm, ReembolsarEgresoForm
from .models import Egreso, Ingreso
from .push_handlers import notificar_reembolso_pendiente

# ── Helpers ────────────────────────────────────────────────────────────────


def _gate(request):
    if not puede_ver_finanzas(request.user):
        return HttpResponseForbidden("Sin acceso a Tesorería.")
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
    # S-LC-Feedback-V5 c8: metas KPI con barra de progreso.
    from apps.taller_home.services_meta_kpi import enriquecer_con_meta
    meta_ingresos = enriquecer_con_meta({"valor": kpis_fmt["ingresos_mes_fmt"]}, "ingresos-mes", valor_numerico=float(kpis["ingresos_mes"]))
    meta_egresos = enriquecer_con_meta({"valor": kpis_fmt["egresos_mes_fmt"]}, "egresos-mes", valor_numerico=float(kpis["egresos_mes"]))
    meta_utilidad = enriquecer_con_meta({"valor": kpis_fmt["utilidad_mes_fmt"]}, "utilidad-mes", valor_numerico=float(kpis["utilidad_mes"]))
    # Sparklines 30 días — JSON inline en data-series del partial.
    import json as _json
    series = services.series_diarias_30d()
    spark_ingresos = _json.dumps(series["ingresos"])
    spark_egresos = _json.dumps(series["egresos"])
    spark_utilidad = _json.dumps(series["utilidad"])
    return render(request, "tesoreria/landing.html", {
        "kpis": kpis_fmt,
        "charts": services.charts_landing(),
        "ultimos_ingresos": Ingreso.vigentes.all()[:5],
        "ultimos_egresos": Egreso.vigentes.all()[:5],
        "meta_ingresos": meta_ingresos,
        "meta_egresos": meta_egresos,
        "meta_utilidad": meta_utilidad,
        "spark_ingresos": spark_ingresos,
        "spark_egresos": spark_egresos,
        "spark_utilidad": spark_utilidad,
    })


# ── Ingresos ───────────────────────────────────────────────────────────────


@login_required
def ingresos_lista(request):
    if (r := _gate(request)) is not None:
        return r
    from django.core.paginator import Paginator
    qs = Ingreso.objects.all() if request.GET.get("anulados") == "1" else Ingreso.vigentes.all()
    qs = qs.select_related("cliente", "proyecto", "creado_por")
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(descripcion__icontains=q)
    orden_permitido = {"codigo", "fecha", "monto"}
    orden = (request.GET.get("orden") or "-fecha").strip()
    if orden.lstrip("-") not in orden_permitido:
        orden = "-fecha"
    qs = qs.order_by(orden, "-pk")
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    qs_filtros = []
    if q:
        qs_filtros.append(f"q={q}")
    if request.GET.get("anulados") == "1":
        qs_filtros.append("anulados=1")
    return render(request, "tesoreria/ingresos_lista.html", {
        "ingresos": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "incluye_anulados": request.GET.get("anulados") == "1",
        "orden_actual": orden,
        "querystring_base": "&".join(qs_filtros),
        "querystring_paginacion": "&".join(qs_filtros + ([f"orden={orden}"] if orden != "-fecha" else [])),
        "cabeceras_ingresos": [
            {"label": "Código", "sort_key": "codigo"},
            {"label": "Fecha", "sort_key": "fecha"},
            {"label": "Cliente · Proyecto"},
            {"label": "Método"},
            {"label": "Monto", "sort_key": "monto", "align": "right"},
            {"label": "", "align": "right"},
        ],
    })


@login_required
def ingreso_detalle(request, pk):
    if (r := _gate(request)) is not None:
        return r
    ingreso = get_object_or_404(Ingreso, pk=pk)
    info_clasificacion = [
        {"label": "Cliente", "value": ingreso.cliente.razon_social if ingreso.cliente else "—"},
        {"label": "Proyecto", "value": f"{ingreso.proyecto.codigo} · {ingreso.proyecto.nombre}" if ingreso.proyecto else "—"},
        {"label": "Método", "value": ingreso.get_metodo_display()},
        {"label": "Ref. externa", "value": ingreso.referencia_externa or "—"},
    ]
    info_captura = [
        {"label": "Capturado por", "value": (ingreso.creado_por.nombre_completo or ingreso.creado_por.email) if ingreso.creado_por else "—"},
        {"label": "Capturado en", "value": ingreso.creado_en.strftime("%Y-%m-%d %H:%M")},
    ]
    action_bar_meta = format_html(
        '<span class="font-mono">{}</span> <span class="text-gray-400">·</span> <span>{}</span>',
        ingreso.codigo, ingreso.fecha.strftime("%Y-%m-%d"),
    )
    if ingreso.anulado:
        action_bar_acciones = format_html(
            '<a href="{}" class="btn-secundario">← Ingresos</a>',
            reverse("tesoreria:ingresos-lista"),
        )
    else:
        action_bar_acciones = format_html(
            '<a href="{}" class="btn-secundario">← Ingresos</a>'
            '<a href="{}" class="btn-secundario">Editar</a>'
            '<button type="button" class="btn-destructivo" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML">Anular</button>',
            reverse("tesoreria:ingresos-lista"),
            reverse("tesoreria:ingreso-editar", args=[ingreso.pk]),
            reverse("tesoreria:ingreso-anular", args=[ingreso.pk]),
        )
    return render(request, "tesoreria/ingreso_detalle.html", {
        "ingreso": ingreso,
        "info_clasificacion": info_clasificacion,
        "info_captura": info_captura,
        "action_bar_meta": action_bar_meta,
        "action_bar_acciones": action_bar_acciones,
        "breadcrumb_items": [
            {"url": reverse("tesoreria:landing"), "label": "Tesorería"},
            {"url": reverse("tesoreria:ingresos-lista"), "label": "Ingresos"},
            {"label": ingreso.codigo},
        ],
        "back_url": reverse("tesoreria:ingresos-lista"),
        "back_label": "Ingresos",
    })


def _next_seguro(request):
    """URL interna a la que volver tras guardar (ej. el proyecto de origen)."""
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    return nxt if nxt.startswith("/") and "//" not in nxt[1:3] else ""


def _ingreso_pickers(request):
    """Quick-pick: 6 clientes/proyectos más recientes + flag de alta inline."""
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto

    from lib.permisos import puede_editar_cartera
    return {
        "clientes_recientes": list(Cliente.activos.all().order_by("-actualizado_en")[:6]),
        "proyectos_recientes": list(
            Proyecto.objects.exclude(estado__in=["cancelado", "cerrado"]).order_by("-actualizado_en")[:6]
        ),
        "puede_crear_cliente": puede_editar_cartera(request.user),
    }


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
            return redirect(_next_seguro(request) or "tesoreria:landing")
    else:
        initial = {}
        if request.GET.get("proyecto"):
            initial["proyecto"] = request.GET.get("proyecto")
        form = IngresoForm(initial=initial)
    return render(request, "tesoreria/ingreso_form.html",
                  {"form": form, "modo": "nuevo", "next_url": _next_seguro(request), **_ingreso_pickers(request)})


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
                  {"form": form, "modo": "editar", "ingreso": ingreso, **_ingreso_pickers(request)})


@login_required
def ingreso_anular(request, pk):
    if (r := _gate(request)) is not None:
        return r
    ingreso = get_object_or_404(Ingreso, pk=pk)
    if ingreso.anulado:
        return redirect("tesoreria:ingreso-detalle", pk=ingreso.pk)
    es_htmx = request.headers.get("HX-Request") == "true"
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
            destino = reverse("tesoreria:ingreso-detalle", args=[ingreso.pk])
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": destino})
            return redirect(destino)
    else:
        form = AnularForm()
    template = "tesoreria/_modal_anular.html" if es_htmx else "tesoreria/anular.html"
    return render(request, template, {"form": form, "objeto": ingreso, "tipo": "ingreso"})


# ── Egresos ────────────────────────────────────────────────────────────────


@login_required
def egresos_lista(request):
    if (r := _gate(request)) is not None:
        return r
    from django.core.paginator import Paginator
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
    orden_permitido = {"codigo", "fecha", "monto", "estado_pago"}
    orden = (request.GET.get("orden") or "-fecha").strip()
    if orden.lstrip("-") not in orden_permitido:
        orden = "-fecha"
    qs = qs.order_by(orden, "-pk")
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    qs_filtros = []
    if q:
        qs_filtros.append(f"q={q}")
    if centro:
        qs_filtros.append(f"centro={centro}")
    if estado:
        qs_filtros.append(f"estado_pago={estado}")
    if request.GET.get("anulados") == "1":
        qs_filtros.append("anulados=1")
    querystring_base = "&".join(qs_filtros)
    from .models import CentroDeCosto
    return render(request, "tesoreria/egresos_lista.html", {
        "egresos": page_obj.object_list,
        "page_obj": page_obj,
        "q": q, "centro": centro, "estado_pago": estado,
        "orden_actual": orden,
        "querystring_base": querystring_base,
        "querystring_paginacion": "&".join(qs_filtros + ([f"orden={orden}"] if orden != "-fecha" else [])),
        "cabeceras_egresos": [
            {"label": "Código", "sort_key": "codigo"},
            {"label": "Fecha", "sort_key": "fecha"},
            {"label": "Proveedor · Proyecto"},
            {"label": "Centro"},
            {"label": "Estado", "sort_key": "estado_pago"},
            {"label": "Monto", "sort_key": "monto", "align": "right"},
            {"label": "", "align": "right"},
        ],
        "centros": CentroDeCosto.objects.filter(activo=True),
        "incluye_anulados": request.GET.get("anulados") == "1",
    })


@login_required
def egreso_detalle(request, pk):
    if (r := _gate(request)) is not None:
        return r
    egreso = get_object_or_404(Egreso, pk=pk)
    estado_pago_clase = {
        "pagado": "badge-success",
        "por_reembolsar": "badge-warning",
    }.get(egreso.estado_pago, "badge-gray")
    info_clasificacion = [
        {"label": "Centro de costo", "value": egreso.centro_de_costo.nombre},
        {"label": "Proyecto", "value": f"{egreso.proyecto.codigo} · {egreso.proyecto.nombre}" if egreso.proyecto else "—"},
        {"label": "Origen", "value": egreso.get_origen_display() + (f" · confianza {egreso.confianza_ia:.2f}" if egreso.confianza_ia else "")},
    ]
    info_pago = [
        {"label": "Estado", "value_html": format_html(
            '<span class="badge {}">{}</span>', estado_pago_clase, egreso.get_estado_pago_display(),
        )},
        {"label": "Método", "value": egreso.get_metodo_display()},
        {"label": "Pagado por", "value": (egreso.pagado_por.nombre_completo or egreso.pagado_por.email) if egreso.pagado_por else "—"},
        {"label": "Solicitado por", "value": (egreso.solicitado_por.nombre_completo or egreso.solicitado_por.email) if egreso.solicitado_por else "—"},
        {"label": "Proveedor", "value": egreso.proveedor_nombre or "—"},
    ]
    if egreso.pagado_en:
        info_pago.insert(2, {
            "label": "Fecha de pago",
            "value_html": format_html(
                '<span class="font-medium text-success-700 dark:text-success-400">{}</span>'
                '<span class="ml-1 text-xs text-gray-500">desde {}</span>',
                egreso.pagado_en.strftime("%Y-%m-%d"),
                egreso.get_pagado_desde_display() or "—",
            ),
        })
    info_captura = [
        {"label": "Capturado por", "value": (egreso.creado_por.nombre_completo or egreso.creado_por.email) if egreso.creado_por else "—"},
        {"label": "Capturado en", "value": egreso.creado_en.strftime("%Y-%m-%d %H:%M")},
    ]
    action_bar_meta = format_html(
        '<span class="font-mono">{}</span> <span class="text-gray-400">·</span> <span>{}</span>',
        egreso.codigo, egreso.fecha.strftime("%Y-%m-%d"),
    )
    if egreso.anulado:
        action_bar_acciones = format_html(
            '<a href="{}" class="btn-secundario">← Egresos</a>',
            reverse("tesoreria:egresos-lista"),
        )
    else:
        action_bar_acciones = format_html(
            '<a href="{}" class="btn-secundario">← Egresos</a>'
            '<a href="{}" class="btn-secundario">Editar</a>'
            '<button type="button" class="btn-destructivo" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML">Anular</button>',
            reverse("tesoreria:egresos-lista"),
            reverse("tesoreria:egreso-editar", args=[egreso.pk]),
            reverse("tesoreria:egreso-anular", args=[egreso.pk]),
        )
    return render(request, "tesoreria/egreso_detalle.html", {
        "egreso": egreso,
        "info_clasificacion": info_clasificacion,
        "info_pago": info_pago,
        "info_captura": info_captura,
        "action_bar_meta": action_bar_meta,
        "action_bar_acciones": action_bar_acciones,
        "breadcrumb_items": [
            {"url": reverse("tesoreria:landing"), "label": "Tesorería"},
            {"url": reverse("tesoreria:egresos-lista"), "label": "Egresos"},
            {"label": egreso.codigo},
        ],
        "back_url": reverse("tesoreria:egresos-lista"),
        "back_label": "Egresos",
    })


def _procesar_comprobante(request, egreso) -> None:
    """Sube el comprobante del egreso a Drive y popula los campos drive_*.

    Fallback gracioso: si Drive cae o el archivo es inválido, el egreso ya
    quedó guardado; sólo avisamos con messages.
    """
    archivo = request.FILES.get("comprobante")
    if not archivo:
        return
    from lib.adjuntos import subir
    res = subir(archivo, subcarpeta="Comprobantes")
    if res.ok and res.data:
        egreso.drive_file_id = res.data["id"]
        egreso.drive_url_view = res.data.get("webViewLink", "")
        egreso.tiene_comprobante = True
        egreso.save(update_fields=["drive_file_id", "drive_url_view", "tiene_comprobante"])
        messages.success(request, "Comprobante guardado en Drive.")
    else:
        messages.warning(request, f"Comprobante no subido: {res.error}")


@login_required
def egreso_comprobante(request, pk):
    """Sirve el comprobante del egreso desde Drive (proxy autenticado, sin liga
    pública). Lo ve cualquiera con acceso a Tesorería."""
    if (r := _gate(request)) is not None:
        return r
    from urllib.parse import quote

    egreso = get_object_or_404(Egreso, pk=pk)
    if not (egreso.tiene_comprobante and egreso.drive_file_id):
        raise Http404("Este egreso no tiene comprobante.")

    from lib.google_drive import drive
    try:
        contenido, mime, nombre = drive.descargar(egreso.drive_file_id)
    except Exception:  # noqa: BLE001
        raise Http404("No se pudo obtener el comprobante de Drive.") from None

    resp = HttpResponse(contenido, content_type=mime or "application/octet-stream")
    disposicion = "inline" if (mime or "").startswith(("image/", "application/pdf")) else "attachment"
    resp["Content-Disposition"] = f"{disposicion}; filename*=UTF-8''{quote(nombre)}"
    return resp


@login_required
def egreso_nuevo(request):
    if (r := _gate(request)) is not None:
        return r
    if request.method == "POST":
        form = EgresoForm(request.POST, request.FILES)
        if form.is_valid():
            egreso = form.save(commit=False)
            egreso.creado_por = request.user
            if not egreso.pagado_por:
                egreso.pagado_por = request.user
            egreso.save()
            _vincular_proveedor_a_proyecto(egreso)
            _procesar_comprobante(request, egreso)
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
            return redirect(_next_seguro(request) or "tesoreria:landing")
    else:
        initial = {}
        pk = request.GET.get("proyecto")
        if pk:
            initial["proyecto"] = pk
            from apps.el_catalogo.models import Proveedor
            prov = Proveedor.objects.filter(
                activo=True, servicios__en_proyectos__proyecto_id=pk,
            ).first()
            if prov:
                initial["proveedor"] = prov.pk
        form = EgresoForm(initial=initial)
    return render(request, "tesoreria/egreso_form.html",
                  {"form": form, "modo": "nuevo", "next_url": _next_seguro(request)})


def _vincular_proveedor_a_proyecto(egreso):
    """Si el egreso liga proyecto + proveedor y el proveedor no estaba asignado
    al proyecto, lo asigna (S-LC-Buzon: 'lo liga con el proveedor... o lo asigna
    al crear el gasto si no existía')."""
    if not (egreso.proyecto_id and egreso.proveedor_id):
        return
    from apps.los_proyectos.models.proveedor_proyecto import ProyectoProveedor
    ProyectoProveedor.objects.get_or_create(
        proyecto_id=egreso.proyecto_id, proveedor_id=egreso.proveedor_id,
    )


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
        form = EgresoForm(request.POST, request.FILES, instance=egreso)
        if form.is_valid():
            form.save()
            _procesar_comprobante(request, egreso)
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
    es_htmx = request.headers.get("HX-Request") == "true"
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
            destino = reverse("tesoreria:egreso-detalle", args=[egreso.pk])
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": destino})
            return redirect(destino)
    else:
        form = AnularForm()
    template = "tesoreria/_modal_anular.html" if es_htmx else "tesoreria/anular.html"
    return render(request, template, {"form": form, "objeto": egreso, "tipo": "egreso"})


@login_required
def egreso_reembolsar(request, pk):
    if (r := _gate(request)) is not None:
        return r
    egreso = get_object_or_404(Egreso, pk=pk)
    es_htmx = request.headers.get("HX-Request") == "true"
    if egreso.anulado or egreso.estado_pago != "por_reembolsar":
        messages.error(request, "Sólo egresos 'por reembolsar' vigentes pueden reembolsarse.")
        destino = reverse("tesoreria:egreso-detalle", args=[egreso.pk])
        if es_htmx:
            return HttpResponse(status=204, headers={"HX-Redirect": destino})
        return redirect(destino)
    if request.method == "POST":
        form = ReembolsarEgresoForm(request.POST)
        if form.is_valid():
            resultado = services.reembolsar_egreso(
                egreso,
                metodo=form.cleaned_data["metodo"],
                banco_o_caja=form.cleaned_data["banco_o_caja"],
                fecha=form.cleaned_data["fecha"],
                actor=request.user,
            )
            messages.success(request, f"Reembolso de {egreso.codigo} registrado.")
            if not getattr(resultado, "_reembolso_asiento_creado", True):
                motivo = getattr(resultado, "_reembolso_motivo_no_asiento", "")
                messages.warning(
                    request,
                    f"⚠ El pago se registró pero el movimiento contable NO se generó: "
                    f"{motivo} Avisa al super_admin para que revise el catálogo "
                    f"de cuentas en Contaduría.",
                )
            destino = reverse("tesoreria:por-pagar")
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": destino})
            return redirect(destino)
    else:
        form = ReembolsarEgresoForm()
    template = "tesoreria/_modal_reembolsar.html" if es_htmx else "tesoreria/reembolsar.html"
    return render(request, template, {"form": form, "egreso": egreso})


# ── Cuentas por cobrar / pagar ─────────────────────────────────────────────


@login_required
def por_cobrar(request):
    if (r := _gate(request)) is not None:
        return r
    filas = services.cxc_unificado()
    total = sum((f["saldo"] for f in filas), Decimal("0"))
    # Conteo por tipo para el header
    cuenta_facturas = sum(1 for f in filas if f["tipo"] == "factura")
    cuenta_anticipos = sum(1 for f in filas if f["tipo"] == "anticipo")
    cuenta_proyectos = sum(1 for f in filas if f["tipo"] == "proyecto")
    return render(request, "tesoreria/por_cobrar.html", {
        "filas": filas,
        "total": total,
        "cuenta_facturas": cuenta_facturas,
        "cuenta_anticipos": cuenta_anticipos,
        "cuenta_proyectos": cuenta_proyectos,
        "cabeceras_cobrar": [
            {"label": "Origen"},
            {"label": "Código"},
            {"label": "Cliente"},
            {"label": "Emisión", "align": "right"},
            {"label": "Vencimiento", "align": "right"},
            {"label": "Saldo", "align": "right"},
            {"label": "Estado"},
        ],
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
    egresos_reembolsar = (
        Egreso.vigentes.filter(estado_pago="por_reembolsar")
        .select_related("pagado_por", "centro_de_costo")
        .order_by("pagado_por__email", "fecha")
    )
    return render(request, "tesoreria/por_pagar.html", {
        "egresos": qs, "estado_pago": estado, "total": total,
        "reembolsos": services.reembolsos_pendientes(),
        "egresos_reembolsar": egresos_reembolsar,
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


# ── API JSON para autocompletar ingreso ──────────────────────────────────

@login_required
def api_proyecto_datos(request, pk):
    """Datos del proyecto para auto-llenar el form de ingreso.

    GET /tesoreria/api/proyecto/<pk>/datos/
    → {id, codigo, nombre, cliente_id, cliente_nombre, monto_pendiente}
    """
    if (r := _gate(request)) is not None:
        return r
    from apps.los_proyectos.models import Proyecto
    proyecto = get_object_or_404(
        Proyecto.objects.select_related("cliente"), pk=pk,
    )
    monto_pendiente = (proyecto.monto_facturado or Decimal("0")) - (proyecto.monto_cobrado or Decimal("0"))
    return JsonResponse({
        "id": proyecto.pk,
        "codigo": proyecto.codigo,
        "nombre": proyecto.nombre,
        "cliente_id": proyecto.cliente_id,
        "cliente_nombre": proyecto.cliente.razon_social if proyecto.cliente else "",
        "monto_pendiente": str(monto_pendiente if monto_pendiente > 0 else 0),
        "descripcion_sugerida": f"Cobro de {proyecto.codigo} · {proyecto.nombre}",
    })
