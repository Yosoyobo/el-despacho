"""Views de Facturación."""

from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ajustes.models.tasa import TasaImpositiva
from lib.permisos import (
    puede_cancelar_facturacion,
    puede_cobrar_facturacion,
    puede_crear_facturacion,
    puede_editar_facturacion,
    puede_emitir_facturacion,
    puede_ver_facturacion,
)

from . import services
from .forms import (
    CancelarForm,
    EmitirForm,
    FacturaForm,
    ItemFormSet,
    RegistrarCobroForm,
)
from .models import Factura, FacturaImpuesto

ORDEN_PERMITIDO = {"codigo", "fecha_emision", "fecha_vencimiento", "estado", "creado_en"}


def _gate_ver(request):
    if not puede_ver_facturacion(request.user):
        return HttpResponseForbidden("Sin acceso a Facturación.")
    return None


def _es_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _hx_redirect(url: str) -> HttpResponse:
    return HttpResponse(status=204, headers={"HX-Redirect": url})


# ── Lista ────────────────────────────────────────────────────────────────


@login_required
def lista(request):
    if (r := _gate_ver(request)) is not None:
        return r

    q = (request.GET.get("q") or "").strip()
    estado_filtro = (request.GET.get("estado") or "").strip()
    qs = Factura.objects.select_related("cliente", "proyecto").exclude(estado="cancelada")
    if estado_filtro:
        if estado_filtro == "cancelada":
            qs = Factura.objects.select_related("cliente", "proyecto").filter(estado="cancelada")
        elif estado_filtro in {"borrador", "emitida", "cobrada_parcial", "cobrada_total"}:
            qs = qs.filter(estado=estado_filtro)
    if q:
        qs = qs.filter(
            Q(codigo__icontains=q)
            | Q(titulo__icontains=q)
            | Q(cliente__razon_social__icontains=q)
        )

    orden = (request.GET.get("orden") or "-creado_en").strip()
    base = orden.lstrip("-")
    if base not in ORDEN_PERMITIDO:
        orden = "-creado_en"
    qs = qs.order_by(orden, "-pk")

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    qs_filtros = []
    if q:
        qs_filtros.append(f"q={q}")
    if estado_filtro:
        qs_filtros.append(f"estado={estado_filtro}")
    querystring_base = "&".join(qs_filtros)
    qs_paginacion = qs_filtros + ([f"orden={orden}"] if orden != "-creado_en" else [])

    return render(request, "facturacion/lista.html", {
        "page_obj": page_obj,
        "facturas": page_obj.object_list,
        "q": q,
        "estado_filtro": estado_filtro,
        "orden_actual": orden,
        "querystring_base": querystring_base,
        "querystring_paginacion": "&".join(qs_paginacion),
        "cabeceras_facturas": [
            {"label": "Código", "sort_key": "codigo"},
            {"label": "Cliente"},
            {"label": "Concepto"},
            {"label": "Emisión", "sort_key": "fecha_emision"},
            {"label": "Total con IVA", "align": "right"},
            {"label": "Estado", "sort_key": "estado"},
        ],
        "kpis": services.kpis_landing(),
        "puede_crear": puede_crear_facturacion(request.user),
    })


# ── Form helpers ─────────────────────────────────────────────────────────


def _ctx_form(form, formset, *, modo: str, fac: Factura | None = None,
              tasas_qs=None, tasas_seleccionadas=None):
    # S-LC-Feedback-V5 c3: categorías para el quick-create de servicio inline.
    from apps.el_catalogo.models import CategoriaServicio
    categorias = CategoriaServicio.objects.filter(activa=True).order_by("orden", "nombre")
    return {
        "form": form,
        "formset": formset,
        "modo": modo,
        "fac": fac,
        "tasas": tasas_qs if tasas_qs is not None else TasaImpositiva.objects.filter(activa=True),
        "tasas_seleccionadas": set(tasas_seleccionadas or []),
        "categorias_disponibles": categorias,
    }


def _persistir_impuestos(fac: Factura, ids_seleccionadas: list[int]):
    deseadas = set(ids_seleccionadas)
    actuales = set(fac.impuestos.values_list("tasa_id", flat=True))
    a_agregar = deseadas - actuales
    a_borrar = actuales - deseadas
    if a_borrar:
        fac.impuestos.filter(tasa_id__in=a_borrar).delete()
    for tid in a_agregar:
        FacturaImpuesto.objects.create(factura=fac, tasa_id=tid)


def _ids_tasas(request) -> list[int]:
    import contextlib
    raw = request.POST.getlist("tasas")
    out = []
    for v in raw:
        with contextlib.suppress(TypeError, ValueError):
            out.append(int(v))
    return out


# ── Crear / editar ───────────────────────────────────────────────────────


@login_required
def nueva(request):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_crear_facturacion(request.user):
        return HttpResponseForbidden("Sin permiso para crear facturas.")

    tasas_qs = TasaImpositiva.objects.filter(activa=True)
    default_ids = list(tasas_qs.filter(aplicable_default=True).values_list("id", flat=True))

    if request.method == "POST":
        form = FacturaForm(request.POST)
        formset = ItemFormSet(request.POST, instance=Factura())
        ids = _ids_tasas(request)
        if form.is_valid() and formset.is_valid():
            fac = form.save(commit=False)
            fac.creado_por = request.user
            fac.save()
            formset.instance = fac
            formset.save()
            _persistir_impuestos(fac, ids)
            services.emitir_creada(fac, request.user)
            messages.success(request, f"Factura {fac.codigo} creada.")
            return redirect("facturacion:detalle", pk=fac.pk)
        ctx = _ctx_form(form, formset, modo="nuevo", tasas_qs=tasas_qs,
                        tasas_seleccionadas=ids)
        return render(request, "facturacion/factura_form.html", ctx)

    form = FacturaForm()
    formset = ItemFormSet(instance=Factura())
    ctx = _ctx_form(form, formset, modo="nuevo", tasas_qs=tasas_qs,
                    tasas_seleccionadas=default_ids)
    return render(request, "facturacion/factura_form.html", ctx)


@login_required
def editar(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    fac = get_object_or_404(Factura, pk=pk)
    if not puede_editar_facturacion(request.user):
        return HttpResponseForbidden("Sin permiso para editar facturas.")
    # Las líneas/impuestos sólo se editan en borrador; el encabezado (estado,
    # concepto, fechas…) se puede corregir en cualquier estado (S-LC-Buzon).
    editable_items = fac.es_editable

    tasas_qs = TasaImpositiva.objects.filter(activa=True)
    ids_actuales = list(fac.impuestos.values_list("tasa_id", flat=True))

    if request.method == "POST":
        form = FacturaForm(request.POST, instance=fac)
        formset = ItemFormSet(request.POST, instance=fac) if editable_items else None
        ids = _ids_tasas(request)
        if form.is_valid() and (formset is None or formset.is_valid()):
            form.save()
            if formset is not None:
                formset.save()
                _persistir_impuestos(fac, ids)
            services.emitir_actualizada(fac, request.user)
            messages.success(request, f"Factura {fac.codigo} actualizada.")
            return redirect("facturacion:detalle", pk=fac.pk)
        ctx = _ctx_form(form, formset, modo="editar", fac=fac, tasas_qs=tasas_qs,
                        tasas_seleccionadas=ids)
        ctx["editable_items"] = editable_items
        return render(request, "facturacion/factura_form.html", ctx)

    form = FacturaForm(instance=fac)
    formset = ItemFormSet(instance=fac) if editable_items else None
    ctx = _ctx_form(form, formset, modo="editar", fac=fac, tasas_qs=tasas_qs,
                    tasas_seleccionadas=ids_actuales)
    ctx["editable_items"] = editable_items
    return render(request, "facturacion/factura_form.html", ctx)


@login_required
def desde_cotizacion(request, cot_pk):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_crear_facturacion(request.user):
        return HttpResponseForbidden("Sin permiso para crear facturas.")
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    from apps.cotizaciones.models import Cotizacion
    cot = get_object_or_404(Cotizacion, pk=cot_pk)
    fac = services.crear_desde_cotizacion(cot, request.user)
    messages.success(request, f"Factura {fac.codigo} creada desde {cot.codigo}.")
    return redirect("facturacion:editar", pk=fac.pk)


# ── Detalle ──────────────────────────────────────────────────────────────


@login_required
def detalle(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    fac = get_object_or_404(
        Factura.objects.select_related("cliente", "proyecto", "creado_por", "cotizacion_origen"),
        pk=pk,
    )
    totales = fac.calcular_totales()
    items = list(fac.items.select_related("servicio").all())

    from apps.tesoreria.models import Egreso, Ingreso
    cobros = list(Ingreso.vigentes.filter(factura=fac).order_by("-fecha", "-pk"))
    # Movimientos del proyecto ligado (S-LC-Buzon): se muestran abajo del detalle.
    ingresos_proyecto, egresos_proyecto = [], []
    if fac.proyecto_id:
        ingresos_proyecto = list(Ingreso.vigentes.filter(proyecto_id=fac.proyecto_id).order_by("-fecha")[:50])
        egresos_proyecto = list(Egreso.vigentes.filter(proyecto_id=fac.proyecto_id).select_related("proveedor").order_by("-fecha")[:50])

    info_cliente = [
        {"label": "Razón social", "value": fac.cliente.razon_social},
        {"label": "RFC", "value": getattr(fac.cliente, "rfc", "") or "—", "mono": True},
        {"label": "Contacto", "value": getattr(fac.cliente, "email_contacto", "") or "—"},
        {"label": "Proyecto", "value": fac.proyecto.codigo if fac.proyecto else "—"},
    ]
    info_fechas = [
        {"label": "Emisión", "value": fac.fecha_emision.strftime("%Y-%m-%d")},
        {"label": "Vencimiento", "value": fac.fecha_vencimiento.strftime("%Y-%m-%d")},
        {"label": "Emitida", "value": fac.emitida_en.strftime("%Y-%m-%d %H:%M") if fac.emitida_en else "—"},
        {"label": "Por", "value": fac.emitida_por.nombre_completo if fac.emitida_por else "—"},
    ]
    info_totales = [
        {"label": "Total", "value": f"${totales['total']:,.2f} {fac.moneda}"},
        {"label": "Cobrado", "value": f"${fac.monto_cobrado:,.2f}"},
        {"label": "Saldo", "value": f"${fac.saldo_pendiente:,.2f}"},
    ]
    info_captura = [
        {"label": "Capturada por",
         "value": fac.creado_por.nombre_completo if fac.creado_por else "—"},
        {"label": "Creada", "value": fac.creado_en.strftime("%Y-%m-%d %H:%M")},
        {"label": "Actualizada", "value": fac.actualizado_en.strftime("%Y-%m-%d %H:%M")},
    ]
    info_origen = None
    if fac.cotizacion_origen:
        info_origen = [
            {"label": "Cotización", "value": fac.cotizacion_origen.codigo, "mono": True},
            {"label": "Título", "value": fac.cotizacion_origen.titulo[:80]},
        ]

    # EDITAR disponible en cualquier estado (para corregir estado, concepto,
    # fechas…). Las líneas sólo se editan en borrador (ver vista editar).
    puede_editar = puede_editar_facturacion(request.user)
    puede_emitir_ = puede_emitir_facturacion(request.user) and fac.estado == "borrador"
    puede_cobrar = (
        puede_cobrar_facturacion(request.user)
        and fac.estado in {"emitida", "cobrada_parcial"}
    )
    # Ticket LC 2026-06-29: el botón "Cancelar factura" es ÚNICO y SIEMPRE
    # visible (cualquier estado salvo ya-cancelada). El modal explica el efecto
    # y, si la factura tiene cobros, bloquea con un mensaje claro (hay dinero
    # real recibido — primero se anulan los Ingresos).
    puede_cancelar_ = (
        puede_cancelar_facturacion(request.user)
        and fac.estado != "cancelada"
    )
    puede_duplicar = puede_crear_facturacion(request.user)

    acciones_html: list = []
    acciones_html.append(format_html(
        '<a href="{}" target="_blank" rel="noopener" class="btn-secundario" '
        'title="Genera el PDF con el formato de Learning Center y lo abre en una pestaña nueva.">📄 PDF</a>',
        reverse("facturacion:pdf", args=[fac.pk]),
    ))
    if puede_editar:
        acciones_html.append(format_html(
            '<a href="{}" class="btn-secundario">Editar</a>',
            reverse("facturacion:editar", args=[fac.pk]),
        ))
    if puede_emitir_:
        acciones_html.append(format_html(
            '<button type="button" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML" class="btn-primario">Emitir</button>',
            reverse("facturacion:emitir", args=[fac.pk]),
        ))
    if puede_cobrar:
        acciones_html.append(format_html(
            '<button type="button" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML" class="btn-primario">Registrar cobro</button>',
            reverse("facturacion:cobrar", args=[fac.pk]),
        ))
    if puede_duplicar:
        from django.middleware.csrf import get_token
        token = get_token(request)
        acciones_html.append(format_html(
            '<form method="post" action="{}" class="inline">'
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
            '<button type="submit" class="btn-secundario">Duplicar</button></form>',
            reverse("facturacion:duplicar", args=[fac.pk]),
            token,
        ))
    if puede_cancelar_:
        acciones_html.append(format_html(
            '<button type="button" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML" '
            'class="inline-flex items-center rounded-lg border border-error-300 px-4 py-2 text-sm font-medium '
            'text-error-600 transition hover:bg-error-50 dark:border-error-500/40 dark:text-error-400 dark:hover:bg-error-500/10">'
            'Cancelar factura</button>',
            reverse("facturacion:cancelar", args=[fac.pk]),
        ))

    action_bar_acciones = mark_safe("".join(str(a) for a in acciones_html))
    action_bar_meta = format_html(
        '<span class="text-gray-500">Última actualización {}</span>',
        fac.actualizado_en.strftime("%Y-%m-%d %H:%M"),
    )

    return render(request, "facturacion/factura_detalle.html", {
        "fac": fac,
        "items": items,
        "totales": totales,
        "cobros": cobros,
        "recordatorios": list(fac.recordatorios.order_by("-enviado_en")[:10]),
        "ingresos_proyecto": ingresos_proyecto,
        "egresos_proyecto": egresos_proyecto,
        "info_cliente": info_cliente,
        "info_fechas": info_fechas,
        "info_totales": info_totales,
        "info_captura": info_captura,
        "info_origen": info_origen,
        "action_bar_meta": action_bar_meta,
        "action_bar_acciones": action_bar_acciones,
        "puede_editar": puede_editar,
        "puede_emitir": puede_emitir_,
        "puede_cobrar": puede_cobrar,
        "puede_cancelar": puede_cancelar_,
        "puede_duplicar": puede_duplicar,
    })


# ── Modales HTMX ─────────────────────────────────────────────────────────


def _modal(request, template: str, ctx: dict, status: int = 200):
    return render(request, template, ctx, status=status)


@login_required
def emitir(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    fac = get_object_or_404(Factura, pk=pk)
    if not puede_emitir_facturacion(request.user):
        return HttpResponseForbidden("Sin permiso para emitir facturas.")
    if fac.estado != "borrador":
        messages.error(request, "Solo se puede emitir una factura en borrador.")
        return redirect("facturacion:detalle", pk=fac.pk)
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = EmitirForm(request.POST)
        if form.is_valid():
            services.emitir_factura(fac, request.user)
            # El Cartero entrega la factura por correo con el PDF (best-effort).
            res = services.enviar_por_correo(fac, request.user)
            if res.ok:
                messages.success(request, f"Factura {fac.codigo} emitida y enviada por correo. {res.detalle}")
            else:
                messages.warning(request, f"Factura {fac.codigo} emitida, pero el correo no salió: {res.error}")
            destino = reverse("facturacion:detalle", args=[fac.pk])
            return _hx_redirect(destino) if es_htmx else redirect(destino)
    return _modal(request, "facturacion/_modal_emitir.html",
                  {"fac": fac, "form": EmitirForm()})


@login_required
def registrar_cobro(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    fac = get_object_or_404(Factura, pk=pk)
    if not puede_cobrar_facturacion(request.user):
        return HttpResponseForbidden("Sin permiso para registrar cobros.")
    if fac.estado not in {"emitida", "cobrada_parcial"}:
        messages.error(request, "Solo se puede cobrar facturas emitidas.")
        return redirect("facturacion:detalle", pk=fac.pk)
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = RegistrarCobroForm(request.POST)
        if form.is_valid():
            try:
                services.registrar_cobro(
                    fac,
                    monto=form.cleaned_data["monto"],
                    fecha=form.cleaned_data["fecha"],
                    metodo=form.cleaned_data["metodo"],
                    actor=request.user,
                    banco_o_caja=form.cleaned_data["banco_o_caja"],
                    folio=form.cleaned_data.get("folio", ""),
                    nota=form.cleaned_data.get("nota", ""),
                )
                messages.success(request, f"Cobro registrado en {fac.codigo}.")
                destino = reverse("facturacion:detalle", args=[fac.pk])
                return _hx_redirect(destino) if es_htmx else redirect(destino)
            except ValueError as e:
                form.add_error(None, str(e))
        return _modal(request, "facturacion/_modal_registrar_cobro.html",
                      {"fac": fac, "form": form})
    initial = {"fecha": date.today(), "monto": fac.saldo_pendiente, "metodo": "transferencia"}
    return _modal(request, "facturacion/_modal_registrar_cobro.html",
                  {"fac": fac, "form": RegistrarCobroForm(initial=initial)})


@login_required
def cancelar(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    fac = get_object_or_404(Factura, pk=pk)
    if not puede_cancelar_facturacion(request.user):
        return HttpResponseForbidden("Sin permiso para cancelar facturas.")
    if fac.estado == "cancelada":
        messages.error(request, "La factura ya estaba cancelada.")
        return redirect("facturacion:detalle", pk=fac.pk)
    es_htmx = _es_htmx(request)
    tiene_cobros = (fac.monto_cobrado or 0) > 0
    if request.method == "POST":
        form = CancelarForm(request.POST)
        if form.is_valid():
            try:
                services.cancelar(fac, request.user, form.cleaned_data["motivo"])
                messages.success(request, f"Factura {fac.codigo} cancelada.")
                destino = reverse("facturacion:detalle", args=[fac.pk])
                return _hx_redirect(destino) if es_htmx else redirect(destino)
            except ValueError as e:
                form.add_error(None, str(e))
        return _modal(request, "facturacion/_modal_cancelar.html",
                      {"fac": fac, "form": form, "tiene_cobros": tiene_cobros})
    return _modal(request, "facturacion/_modal_cancelar.html",
                  {"fac": fac, "form": CancelarForm(), "tiene_cobros": tiene_cobros})


@login_required
def duplicar(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_crear_facturacion(request.user):
        return HttpResponseForbidden("Sin permiso para crear facturas.")
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    fac = get_object_or_404(Factura, pk=pk)
    nueva = services.duplicar(fac, request.user)
    messages.success(request, f"Factura duplicada como {nueva.codigo}.")
    return redirect("facturacion:editar", pk=nueva.pk)


# ── API JSON para autocompletar en factura_form ──────────────────────────

@login_required
def api_proyecto_datos(request, pk):
    """Devuelve datos del proyecto para auto-llenar el form de factura.

    GET /facturacion/api/proyecto/<pk>/datos/
    → {cliente_id, cliente_nombre, codigo, cotizaciones: [{id, codigo, titulo, estado}]}
    """
    if (r := _gate_ver(request)) is not None:
        return r
    from apps.cotizaciones.models import Cotizacion
    from apps.los_proyectos.models import Proyecto
    proyecto = get_object_or_404(
        Proyecto.objects.select_related("cliente"), pk=pk,
    )
    cots = Cotizacion.vigentes.filter(proyecto=proyecto).order_by("-creado_en")[:20]
    return JsonResponse({
        "id": proyecto.pk,
        "codigo": proyecto.codigo,
        "nombre": proyecto.nombre,
        "cliente_id": proyecto.cliente_id,
        "cliente_nombre": proyecto.cliente.razon_social if proyecto.cliente else "",
        "cotizaciones": [
            {"id": c.pk, "codigo": c.codigo, "titulo": c.titulo, "estado": c.estado}
            for c in cots
        ],
    })


@login_required
def api_cotizacion_datos(request, pk):
    """Devuelve datos de la cotización para auto-llenar form de factura.

    GET /facturacion/api/cotizacion/<pk>/datos/
    → {cliente_id, cliente_nombre, proyecto_id, proyecto_codigo, titulo,
       descuento_global_porcentaje, notas, terminos, items: [...], impuestos: [tasa_id, ...]}
    """
    if (r := _gate_ver(request)) is not None:
        return r
    from apps.cotizaciones.models import Cotizacion
    cot = get_object_or_404(
        Cotizacion.objects.select_related("cliente", "proyecto"), pk=pk,
    )
    return JsonResponse({
        "id": cot.pk,
        "codigo": cot.codigo,
        "titulo": cot.titulo,
        "estado": cot.estado,
        "cliente_id": cot.cliente_id,
        "cliente_nombre": cot.cliente.razon_social if cot.cliente else "",
        "proyecto_id": cot.proyecto_id,
        "proyecto_codigo": cot.proyecto.codigo if cot.proyecto else "",
        "moneda": cot.moneda,
        "descuento_global_porcentaje": str(cot.descuento_global_porcentaje or 0),
        "notas": cot.notas,
        "terminos": cot.terminos,
        "items": [
            {
                "descripcion": it.descripcion,
                "cantidad": str(it.cantidad),
                "unidad": it.unidad,
                "precio_unitario": str(it.precio_unitario),
                "descuento_porcentaje": str(it.descuento_porcentaje or 0),
            }
            for it in cot.items.all().order_by("orden", "pk")
        ],
        "impuestos": list(cot.impuestos.values_list("tasa_id", flat=True)),
    })


@login_required
def generar_pdf(request, pk):
    """Genera/regenera el PDF de la factura (vía Google Docs) y lo descarga.

    GET puro — cualquiera que pueda ver Facturación puede descargar el PDF.
    Fallback gracioso: si Drive falla, mensaje y vuelve al detalle."""
    if (r := _gate_ver(request)) is not None:
        return r
    fac = get_object_or_404(Factura, pk=pk)
    res = services.generar_pdf(fac, request.user)
    if not res.ok or not res.pdf_bytes:
        messages.error(request, f"No se pudo generar el PDF: {res.error}")
        return redirect("facturacion:detalle", pk=fac.pk)
    resp = HttpResponse(res.pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{fac.codigo}.pdf"'
    return resp
