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
from django.views.decorators.http import require_http_methods

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

ORDEN_PERMITIDO = {"folio", "codigo", "fecha_emision", "fecha_vencimiento", "estado", "creado_en"}
# Máx. de filas fantasma a inyectar por huecos de folio (defensa anti-runaway).
_MAX_GHOSTS = 2000


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

    orden = (request.GET.get("orden") or "-folio").strip()
    base = orden.lstrip("-")
    if base not in ORDEN_PERMITIDO:
        orden = "-folio"
        base = "folio"
    campo = {"folio": "folio_numero"}.get(base, base)
    orden_db = ("-" if orden.startswith("-") else "") + campo
    qs = qs.order_by(orden_db, "-pk")

    # Filas fantasma «Sin información» para huecos en la secuencia de folios
    # (LC 2026-07). Solo al ordenar por folio y sin filtros/búsqueda.
    usa_ghosts = base == "folio" and not q and not estado_filtro
    if usa_ghosts:
        reales = list(qs)
        con_folio = [f for f in reales if f.folio_numero]
        sin_folio = [f for f in reales if not f.folio_numero]
        combinada: list = []
        if con_folio:
            por_num = {f.folio_numero: f for f in con_folio}
            lo, hi = min(por_num), max(por_num)
            if (hi - lo) <= _MAX_GHOSTS:
                rango = range(hi, lo - 1, -1) if orden.startswith("-") else range(lo, hi + 1)
                for n in rango:
                    combinada.append(por_num.get(n) or {"ghost": True, "folio_numero": n})
            else:
                combinada = con_folio
        combinada.extend(sin_folio)
        objetos = combinada
    else:
        objetos = qs

    paginator = Paginator(objetos, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    qs_filtros = []
    if q:
        qs_filtros.append(f"q={q}")
    if estado_filtro:
        qs_filtros.append(f"estado={estado_filtro}")
    querystring_base = "&".join(qs_filtros)
    qs_paginacion = qs_filtros + ([f"orden={orden}"] if orden != "-folio" else [])

    return render(request, "facturacion/lista.html", {
        "page_obj": page_obj,
        "facturas": page_obj.object_list,
        "q": q,
        "estado_filtro": estado_filtro,
        "orden_actual": orden,
        "querystring_base": querystring_base,
        "querystring_paginacion": "&".join(qs_paginacion),
        "cabeceras_facturas": [
            {"label": "Factura", "sort_key": "folio"},
            {"label": "Cliente"},
            {"label": "Concepto"},
            {"label": "Emisión", "sort_key": "fecha_emision"},
            {"label": "Total pagable", "align": "right"},
            {"label": "Estado", "sort_key": "estado"},
        ],
        "kpis": services.kpis_landing(),
        "pills_estados": [
            ("", "Vigentes"),
            ("borrador", "Borradores"),
            ("emitida", "Emitidas"),
            ("cobrada_parcial", "Cobro parcial"),
            ("cobrada_total", "Cobradas"),
            ("cancelada", "Canceladas"),
        ],
        "puede_crear": puede_crear_facturacion(request.user),
    })


# ── Form helpers ─────────────────────────────────────────────────────────


def _cfg_fiscal_ctx() -> dict:
    """Tasas del régimen (para el preview en vivo del total). Nunca lanza."""
    try:
        from ajustes.models import ConfiguracionFiscal
        cfg = ConfiguracionFiscal.obtener()
        return {
            "iva_tasa": str(cfg.iva_tasa),
            "ret_isr": str(cfg.ret_isr_honorarios),
            "ret_iva_num": str(cfg.ret_iva_honorarios_num or 2),
            "ret_iva_den": str(cfg.ret_iva_honorarios_den or 3),
        }
    except Exception:  # noqa: BLE001
        return {"iva_tasa": "16", "ret_isr": "1.25", "ret_iva_num": "2", "ret_iva_den": "3"}


def _ctx_form(form, formset, *, modo: str, fac: Factura | None = None,
              tasas_qs=None, tasas_seleccionadas=None):
    return {
        "form": form,
        "formset": formset,
        "modo": modo,
        "fac": fac,
        "tasas": tasas_qs if tasas_qs is not None else TasaImpositiva.objects.filter(activa=True),
        "tasas_seleccionadas": set(tasas_seleccionadas or []),
        "cfg_fiscal": _cfg_fiscal_ctx(),
    }


def _procesar_cfdi(request, fac: Factura):
    """Adjunta / borra el CFDI (PDF + XML) desde el propio form de la factura
    (LC revisión buzón — sin modal aparte). Un solo campo multi-archivo:
    clasifica cada archivo por extensión. Best-effort; nunca tumba el guardado."""
    if request.POST.get("cfdi_borrar_pdf") and fac.pdf_file_id:
        services.borrar_cfdi_archivo(fac, "pdf")
    if request.POST.get("cfdi_borrar_xml") and fac.xml_file_id:
        services.borrar_cfdi_archivo(fac, "xml")
    pdf_file = xml_file = None
    for f in request.FILES.getlist("cfdi_archivos"):
        nombre = (getattr(f, "name", "") or "").lower()
        if nombre.endswith(".xml") and xml_file is None:
            xml_file = f
        elif nombre.endswith(".pdf") and pdf_file is None:
            pdf_file = f
    uuid = (request.POST.get("cfdi_uuid") or "").strip()
    if pdf_file or xml_file or uuid:
        res = services.almacenar_cfdi(
            fac, pdf_file=pdf_file, xml_file=xml_file, cfdi_uuid=uuid, actor=request.user,
        )
        if res["guardados"]:
            messages.success(request, "CFDI: " + ", ".join(res["guardados"]) + " almacenado(s).")
        if res["errores"]:
            messages.warning(request, "CFDI: " + " · ".join(res["errores"]))


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
            # Fix del bug $0.00 (LC revisión buzón): si no se capturaron líneas,
            # el monto se toma del origen (cotización o subtotal del proyecto).
            services.asegurar_lineas_desde_origen(fac)
            _procesar_cfdi(request, fac)
            services.emitir_creada(fac, request.user)
            messages.success(request, f"Factura {fac.codigo} creada.")
            return redirect("facturacion:detalle", pk=fac.pk)
        ctx = _ctx_form(form, formset, modo="nuevo", tasas_qs=tasas_qs,
                        tasas_seleccionadas=ids)
        return render(request, "facturacion/factura_form.html", ctx)

    from .models.factura import sugerir_folio_numero
    initial = {
        "folio_numero": sugerir_folio_numero(),
        "estado": "borrador",
        "porcentaje_a_facturar": 100,
    }
    # Precarga al llegar desde el proyecto ("+ Nueva" del recuadro de facturas
    # ligadas — LC revisión buzón). El querystring antes se ignoraba.
    proy_pre = (request.GET.get("proyecto") or "").strip()
    if proy_pre.isdigit():
        from apps.los_proyectos.models import Proyecto
        proy = Proyecto.objects.filter(pk=int(proy_pre)).select_related("cliente").first()
        if proy is not None:
            initial["proyecto"] = proy.pk
            if proy.cliente_id:
                initial["cliente"] = proy.cliente_id
    cli_pre = (request.GET.get("cliente") or "").strip()
    if cli_pre.isdigit() and "cliente" not in initial:
        initial["cliente"] = int(cli_pre)
    form = FacturaForm(initial=initial)
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
                services.asegurar_lineas_desde_origen(fac)
            _procesar_cfdi(request, fac)
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


def _facturas_ligables(proyecto):
    """Facturas vigentes que se pueden ligar al proyecto (todas menos las que
    ya están en él). Las del mismo cliente primero."""
    return list(
        Factura.vigentes.exclude(proyecto=proyecto)
        .select_related("cliente")
        .order_by("-folio_numero", "-creado_en")[:500]
    )


@login_required
def ligar_proyecto(request, proyecto_pk):
    """Liga una factura EXISTENTE a un proyecto (LC revisión buzón — botón
    «Ligar» junto a «+ Nueva» en el recuadro de facturas del proyecto). Modal
    HTMX (patrón Wave 5): GET → partial; POST → 204 + HX-Redirect al detalle."""
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_crear_facturacion(request.user):
        return HttpResponseForbidden("Sin permiso para ligar facturas.")
    from apps.los_proyectos.models import Proyecto
    proyecto = get_object_or_404(Proyecto, pk=proyecto_pk)
    es_htmx = _es_htmx(request)
    destino = reverse("proyectos-detalle", args=[proyecto.pk])
    if request.method == "POST":
        fid = (request.POST.get("factura") or "").strip()
        fac = Factura.vigentes.filter(pk=int(fid)).first() if fid.isdigit() else None
        if fac is None:
            ctx = {"proyecto": proyecto, "facturas": _facturas_ligables(proyecto),
                   "error": "Elige una factura de la lista."}
            return _modal(request, "facturacion/_modal_ligar.html", ctx)
        fac.proyecto = proyecto
        fac.save(update_fields=["proyecto", "actualizado_en"])
        services.emitir_actualizada(fac, request.user)
        messages.success(request, f"Factura {fac.folio_display} ligada al proyecto {proyecto.codigo}.")
        return _hx_redirect(destino) if es_htmx else redirect(destino)
    if not es_htmx:
        return redirect(destino)
    return _modal(request, "facturacion/_modal_ligar.html",
                  {"proyecto": proyecto, "facturas": _facturas_ligables(proyecto)})


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
    # LC #162: "Vista rápida" = HTML imprimible interno (NO es el CFDI). El CFDI
    # fiscal (PDF + XML del PAC) se almacena y se descarga aparte.
    acciones_html.append(format_html(
        '<a href="{}" target="_blank" rel="noopener" class="btn-secundario" '
        'title="Vista rápida del documento. NO es el CFDI fiscal.">👁 Vista rápida</a>',
        reverse("facturacion:ver", args=[fac.pk]),
    ))
    if fac.pdf_file_id:
        acciones_html.append(format_html(
            '<a href="{}" class="btn-secundario" title="PDF del CFDI timbrado por el PAC.">⬇ PDF (CFDI)</a>',
            reverse("facturacion:pdf", args=[fac.pk]),
        ))
    if fac.xml_file_id:
        acciones_html.append(format_html(
            '<a href="{}" class="btn-secundario" title="XML del CFDI timbrado por el PAC.">⬇ XML</a>',
            reverse("facturacion:xml", args=[fac.pk]),
        ))
    if puede_emitir_facturacion(request.user):
        # LC revisión buzón: la carga del CFDI vive en el propio form (sin modal
        # aparte); el botón lleva a Editar, donde está el recuadro de subida.
        acciones_html.append(format_html(
            '<a href="{}" class="btn-secundario">{}</a>',
            reverse("facturacion:editar", args=[fac.pk]),
            "📎 Reemplazar CFDI" if fac.tiene_cfdi else "📎 Cargar CFDI",
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
    # Eliminar PERMANENTE: solo facturas ya canceladas (limpieza de pruebas).
    if fac.estado == "cancelada" and puede_cancelar_facturacion(request.user):
        from django.middleware.csrf import get_token
        token = get_token(request)
        acciones_html.append(format_html(
            '<form method="post" action="{}" class="inline" '
            'onsubmit="return confirm(\'¿Eliminar PERMANENTEMENTE {}? Esta acción no se puede deshacer.\');">'
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
            '<button type="submit" class="inline-flex items-center rounded-lg border border-error-500 bg-error-500 '
            'px-4 py-2 text-sm font-medium text-white transition hover:bg-error-600">Eliminar</button></form>',
            reverse("facturacion:eliminar", args=[fac.pk]), fac.codigo, token,
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


@login_required
def eliminar(request, pk):
    """Elimina permanentemente una factura cancelada (limpieza). POST puro.
    Gateado por el permiso de cancelar (quien puede cancelar puede limpiar)."""
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_cancelar_facturacion(request.user):
        return HttpResponseForbidden("Sin permiso para eliminar facturas.")
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    fac = get_object_or_404(Factura, pk=pk)
    try:
        codigo = services.eliminar(fac, request.user)
        messages.success(request, f"Factura {codigo} eliminada permanentemente.")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("facturacion:detalle", pk=fac.pk)
    return redirect("facturacion:lista")


# ── API JSON para autocompletar en factura_form ──────────────────────────

@login_required
def api_cliente_proyectos(request, pk):
    """Proyectos vigentes de un cliente, para la cascada Cliente → Proyecto.

    GET /facturacion/api/cliente/<pk>/proyectos/
    → {proyectos: [{id, label}]}
    """
    if (r := _gate_ver(request)) is not None:
        return r
    from apps.los_proyectos.models import Proyecto
    mgr = getattr(Proyecto, "activos", Proyecto.objects)
    proys = mgr.filter(cliente_id=pk).order_by("-creado_en")[:200]
    return JsonResponse({
        "proyectos": [{"id": p.pk, "label": f"{p.codigo} · {p.nombre}"} for p in proys],
    })


@login_required
def api_proyecto_datos(request, pk):
    """Datos del proyecto para la cascada Proyecto → Cotización + concepto.

    GET /facturacion/api/proyecto/<pk>/datos/
    → {cliente_id, cliente_nombre, codigo, nombre,
       cotizaciones: [{id, codigo, titulo, estado, label}]}

    La etiqueta de cada cotización sigue el formato pedido por LC:
    «Nombre proyecto - vN - $subtotal +IVA».
    """
    if (r := _gate_ver(request)) is not None:
        return r
    from apps.cotizaciones.models import Cotizacion
    from apps.los_proyectos.models import Proyecto
    proyecto = get_object_or_404(
        Proyecto.objects.select_related("cliente"), pk=pk,
    )
    cots = Cotizacion.vigentes.filter(proyecto=proyecto).order_by("-creado_en")[:20]
    cots_data = []
    for c in cots:
        tot = c.calcular_totales()
        etiqueta = f"{proyecto.nombre} - {c.version_label} - ${tot['subtotal_items']:,.2f}"
        if tot["trasladados"] > 0:
            etiqueta += " +IVA"
        cots_data.append({
            "id": c.pk, "codigo": c.codigo, "titulo": c.titulo,
            "estado": c.estado, "label": etiqueta,
        })
    return JsonResponse({
        "id": proyecto.pk,
        "codigo": proyecto.codigo,
        "nombre": proyecto.nombre,
        "cliente_id": proyecto.cliente_id,
        "cliente_nombre": proyecto.cliente.razon_social if proyecto.cliente else "",
        "cotizaciones": cots_data,
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
def pdf_ver(request, pk):
    """Vista RÁPIDA del documento (HTML imprimible inline, NO es el CFDI). El
    CFDI fiscal (PDF + XML del PAC) se almacena y se descarga aparte. LC #162."""
    if (r := _gate_ver(request)) is not None:
        return r
    fac = get_object_or_404(Factura, pk=pk)
    return HttpResponse(services.construir_html_pdf(fac))


def _servir_drive(file_id: str, nombre_sugerido: str):
    """Proxy autenticado: baja el archivo de Drive por id y lo sirve inline/
    adjunto. 404 si Drive falla (sin liga pública)."""
    from urllib.parse import quote

    from django.http import Http404

    from lib.google_drive import drive
    try:
        contenido, mime, nombre = drive.descargar(file_id)
    except Exception:  # noqa: BLE001
        raise Http404("No se pudo obtener el archivo de Drive.") from None
    resp = HttpResponse(contenido, content_type=mime or "application/octet-stream")
    disp = "inline" if (mime or "").startswith(("application/pdf", "text/")) else "attachment"
    resp["Content-Disposition"] = f"{disp}; filename*=UTF-8''{quote(nombre or nombre_sugerido)}"
    return resp


@login_required
def descargar_pdf(request, pk):
    """Sirve el PDF del CFDI ALMACENADO (del PAC) desde Drive (proxy). LC #162."""
    if (r := _gate_ver(request)) is not None:
        return r
    fac = get_object_or_404(Factura, pk=pk)
    if not fac.pdf_file_id:
        messages.info(request, "Esta factura aún no tiene PDF del CFDI cargado.")
        return redirect("facturacion:detalle", pk=fac.pk)
    return _servir_drive(fac.pdf_file_id, f"{fac.codigo}.pdf")


@login_required
def descargar_xml(request, pk):
    """Sirve el XML del CFDI ALMACENADO (del PAC) desde Drive (proxy). LC #162."""
    if (r := _gate_ver(request)) is not None:
        return r
    fac = get_object_or_404(Factura, pk=pk)
    if not fac.xml_file_id:
        messages.info(request, "Esta factura aún no tiene XML del CFDI cargado.")
        return redirect("facturacion:detalle", pk=fac.pk)
    return _servir_drive(fac.xml_file_id, f"{fac.codigo}.xml")


@login_required
@require_http_methods(["GET", "POST"])
def almacenar_cfdi(request, pk):
    """Carga/reemplaza el CFDI del PAC (PDF + XML + folio fiscal). Modal HTMX
    (patrón Wave 5). Permitido en cualquier estado y aunque el PROYECTO esté
    CERRADO (#148 — el cierre del proyecto no bloquea la carga). Gated `emitir`."""
    if not puede_emitir_facturacion(request.user):
        return HttpResponseForbidden("Sin permiso para cargar el CFDI.")
    fac = get_object_or_404(Factura, pk=pk)
    es_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST":
        res = services.almacenar_cfdi(
            fac,
            pdf_file=request.FILES.get("pdf"),
            xml_file=request.FILES.get("xml"),
            cfdi_uuid=request.POST.get("cfdi_uuid", ""),
            actor=request.user,
        )
        if res["guardados"] or res["ok"]:
            if res["guardados"]:
                messages.success(request, "CFDI almacenado: " + ", ".join(res["guardados"]) + ".")
            else:
                messages.success(request, "Folio fiscal guardado.")
            if res["errores"]:
                messages.warning(request, " · ".join(res["errores"]))
            if es_htmx:
                return HttpResponse(status=204, headers={
                    "HX-Redirect": reverse("facturacion:detalle", args=[fac.pk])})
            return redirect("facturacion:detalle", pk=fac.pk)
        error = " · ".join(res["errores"]) or "No se cargó ningún archivo ni folio."
        if es_htmx:
            return render(request, "facturacion/_modal_cfdi.html", {"fac": fac, "error": error})
        messages.error(request, error)
        return redirect("facturacion:detalle", pk=fac.pk)
    # GET: sólo tiene sentido inyectado por HTMX en #modal-slot.
    if not es_htmx:
        return redirect("facturacion:detalle", pk=fac.pk)
    return render(request, "facturacion/_modal_cfdi.html", {"fac": fac})
