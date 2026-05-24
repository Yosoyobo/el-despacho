"""Views de Las Cotizaciones."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ajustes.models.tasa import TasaImpositiva
from lib.permisos import (
    puede_anular_cotizaciones,
    puede_aprobar_cotizaciones,
    puede_crear_cotizaciones,
    puede_editar_cotizaciones,
    puede_enviar_cotizaciones,
    puede_rechazar_cotizaciones,
    puede_ver_cotizaciones,
)

from . import services
from .forms import (
    AnularForm,
    AprobarForm,
    CotizacionForm,
    EnviarForm,
    ItemFormSet,
    RechazarForm,
)
from .models import Cotizacion, CotizacionImpuesto

ORDEN_PERMITIDO = {"codigo", "titulo", "estado", "fecha_emision", "creado_en"}


def _gate_ver(request):
    if not puede_ver_cotizaciones(request.user):
        return HttpResponseForbidden("Sin acceso a Las Cotizaciones.")
    return None


def _es_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


@login_required
def lista(request):
    if (r := _gate_ver(request)) is not None:
        return r

    q = (request.GET.get("q") or "").strip()
    estado_filtro = (request.GET.get("estado") or "").strip()
    qs = Cotizacion.objects.select_related("cliente", "proyecto").exclude(estado="anulada")
    if estado_filtro in {"borrador", "enviada", "aprobada", "rechazada", "anulada"}:
        if estado_filtro == "anulada":
            qs = Cotizacion.objects.select_related("cliente", "proyecto").filter(estado="anulada")
        else:
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

    return render(request, "cotizaciones/lista.html", {
        "page_obj": page_obj,
        "cotizaciones": page_obj.object_list,
        "q": q,
        "estado_filtro": estado_filtro,
        "orden_actual": orden,
        "querystring_base": querystring_base,
        "querystring_paginacion": "&".join(qs_paginacion),
        "cabeceras_cotizaciones": [
            {"label": "Código", "sort_key": "codigo"},
            {"label": "Título", "sort_key": "titulo"},
            {"label": "Cliente"},
            {"label": "Estado", "sort_key": "estado"},
            {"label": "Emisión", "sort_key": "fecha_emision"},
            {"label": "Total", "align": "right"},
            {"label": "Acciones", "align": "right"},
        ],
        "kpis": services.kpis_landing(),
        "puede_crear": puede_crear_cotizaciones(request.user),
    })


def _ctx_form(form, formset, *, modo: str, cot: Cotizacion | None = None,
              tasas_qs=None, tasas_seleccionadas=None):
    # S-LC-Feedback-V2: unidades del catálogo para poblar el <select> de cada
    # línea (en lugar de un text input libre).
    from apps.el_catalogo.models import Unidad
    unidades = list(Unidad.objects.filter(activa=True).values_list("nombre", flat=True))
    titulo_pagina = "Nueva cotización" if modo == "nuevo" else f"Editar {cot.codigo if cot else ''}".strip()
    return {
        "form": form,
        "formset": formset,
        "modo": modo,
        "cot": cot,
        "titulo_pagina": titulo_pagina,
        "tasas": tasas_qs if tasas_qs is not None else TasaImpositiva.objects.filter(activa=True),
        "tasas_seleccionadas": set(tasas_seleccionadas or []),
        "unidades_disponibles": unidades,
    }


def _autocompletar_lineas_desde_catalogo(formset):
    """S-LC-Feedback-V4: si una línea tiene servicio pero descripción vacía,
    la rellenamos desde el nombre del servicio (+ variación). Si el precio
    unitario es 0 y la variación trae costo, lo usamos como precio sugerido.
    """
    from decimal import Decimal
    for form in formset.forms:
        if form.cleaned_data.get("DELETE"):
            continue
        servicio = form.cleaned_data.get("servicio")
        variacion = form.cleaned_data.get("variacion")
        if servicio and not (form.cleaned_data.get("descripcion") or "").strip():
            partes = [servicio.nombre]
            if variacion:
                partes.append(variacion.nombre)
            form.instance.descripcion = " · ".join(partes)
        precio = form.cleaned_data.get("precio_unitario") or Decimal("0")
        if precio == 0 and variacion is not None:
            costo = getattr(variacion, "costo", None)
            if costo:
                form.instance.precio_unitario = costo


def _persistir_impuestos(cot: Cotizacion, ids_seleccionadas: list[int]):
    deseadas = set(ids_seleccionadas)
    actuales = set(cot.impuestos.values_list("tasa_id", flat=True))
    a_agregar = deseadas - actuales
    a_borrar = actuales - deseadas
    if a_borrar:
        cot.impuestos.filter(tasa_id__in=a_borrar).delete()
    for tid in a_agregar:
        CotizacionImpuesto.objects.create(cotizacion=cot, tasa_id=tid)


def _ids_tasas(request) -> list[int]:
    import contextlib
    raw = request.POST.getlist("tasas")
    out = []
    for v in raw:
        with contextlib.suppress(TypeError, ValueError):
            out.append(int(v))
    return out


@login_required
def nuevo(request):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_crear_cotizaciones(request.user):
        return HttpResponseForbidden("Sin permiso para crear cotizaciones.")

    tasas_qs = TasaImpositiva.objects.filter(activa=True)
    default_ids = list(tasas_qs.filter(aplicable_default=True).values_list("id", flat=True))

    if request.method == "POST":
        form = CotizacionForm(request.POST)
        formset = ItemFormSet(request.POST, instance=Cotizacion())
        ids = _ids_tasas(request)
        if form.is_valid() and formset.is_valid():
            cot = form.save(commit=False)
            cot.creado_por = request.user
            cot.save()
            formset.instance = cot
            _autocompletar_lineas_desde_catalogo(formset)
            formset.save()
            _persistir_impuestos(cot, ids)
            services.emitir_creada(cot, request.user)
            messages.success(request, f"Cotización {cot.codigo} creada.")
            return redirect("cotizaciones:detalle", pk=cot.pk)
        ctx = _ctx_form(form, formset, modo="nuevo", tasas_qs=tasas_qs,
                        tasas_seleccionadas=ids)
        return render(request, "cotizaciones/form.html", ctx)

    form = CotizacionForm()
    formset = ItemFormSet(instance=Cotizacion())
    ctx = _ctx_form(form, formset, modo="nuevo", tasas_qs=tasas_qs,
                    tasas_seleccionadas=default_ids)
    return render(request, "cotizaciones/form.html", ctx)


@login_required
def editar(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    cot = get_object_or_404(Cotizacion, pk=pk)
    if not puede_editar_cotizaciones(request.user):
        return HttpResponseForbidden("Sin permiso para editar cotizaciones.")
    if not cot.es_editable:
        messages.error(request, "Solo se pueden editar cotizaciones en borrador.")
        return redirect("cotizaciones:detalle", pk=cot.pk)

    tasas_qs = TasaImpositiva.objects.filter(activa=True)
    ids_actuales = list(cot.impuestos.values_list("tasa_id", flat=True))

    if request.method == "POST":
        form = CotizacionForm(request.POST, instance=cot)
        formset = ItemFormSet(request.POST, instance=cot)
        ids = _ids_tasas(request)
        if form.is_valid() and formset.is_valid():
            form.save()
            _autocompletar_lineas_desde_catalogo(formset)
            formset.save()
            _persistir_impuestos(cot, ids)
            services.emitir_actualizada(cot, request.user)
            messages.success(request, f"Cotización {cot.codigo} actualizada.")
            return redirect("cotizaciones:detalle", pk=cot.pk)
        ctx = _ctx_form(form, formset, modo="editar", cot=cot, tasas_qs=tasas_qs,
                        tasas_seleccionadas=ids)
        return render(request, "cotizaciones/form.html", ctx)

    form = CotizacionForm(instance=cot)
    formset = ItemFormSet(instance=cot)
    ctx = _ctx_form(form, formset, modo="editar", cot=cot, tasas_qs=tasas_qs,
                    tasas_seleccionadas=ids_actuales)
    return render(request, "cotizaciones/form.html", ctx)


@login_required
def detalle(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    cot = get_object_or_404(
        Cotizacion.objects.select_related("cliente", "proyecto", "creado_por"),
        pk=pk,
    )
    totales = cot.calcular_totales()
    items = list(cot.items.select_related("servicio").all())

    info_cliente = [
        {"label": "Razón social", "value": cot.cliente.razon_social},
        {"label": "RFC", "value": getattr(cot.cliente, "rfc", "") or "—", "mono": True},
        {"label": "Contacto", "value": getattr(cot.cliente, "email_contacto", "") or "—"},
        {"label": "Proyecto", "value": cot.proyecto.codigo if cot.proyecto else "—"},
    ]
    info_fechas = [
        {"label": "Emisión", "value": cot.fecha_emision.strftime("%Y-%m-%d")},
        {"label": "Validez", "value": cot.fecha_validez.strftime("%Y-%m-%d")},
        {"label": "Enviada", "value": cot.enviada_en.strftime("%Y-%m-%d %H:%M") if cot.enviada_en else "—"},
        {"label": "A", "value": cot.enviada_a_email or "—"},
    ]
    info_aprobacion = [
        {"label": "Aprobada por", "value": cot.aprobada_por_nombre or "—"},
        {"label": "Email", "value": cot.aprobada_por_email or "—"},
        {"label": "Referencia", "value": cot.referencia_aprobacion or "—"},
        {"label": "Fecha", "value": cot.aprobada_en.strftime("%Y-%m-%d %H:%M") if cot.aprobada_en else "—"},
    ]
    info_captura = [
        {"label": "Capturada por", "value": cot.creado_por.nombre_completo if cot.creado_por else "—"},
        {"label": "Creada", "value": cot.creado_en.strftime("%Y-%m-%d %H:%M")},
        {"label": "Actualizada", "value": cot.actualizado_en.strftime("%Y-%m-%d %H:%M")},
    ]
    info_anticipo: list = []
    if (cot.anticipo_porcentaje or 0) > 0 or (cot.anticipo_monto_override or 0) > 0:
        from cuentas.templatetags.forms_helpers import dinero
        info_anticipo = [
            {"label": "Porcentaje", "value": f"{cot.anticipo_porcentaje}%"},
            {"label": "Monto", "value": dinero(cot.anticipo_monto)},
        ]
        if cot.anticipo_monto_override:
            info_anticipo.append({
                "label": "Override",
                "value": dinero(cot.anticipo_monto_override),
            })
        if cot.anticipo_facturado_en:
            info_anticipo.append({
                "label": "Facturado",
                "value_html": format_html(
                    '<span class="text-success-700 dark:text-success-400 font-medium">{}</span>',
                    cot.anticipo_facturado_en.strftime("%Y-%m-%d %H:%M"),
                ),
            })
        elif cot.estado == "aprobada":
            info_anticipo.append({
                "label": "Estado",
                "value_html": format_html(
                    '<span class="text-warning-700 dark:text-warning-400 font-medium">Pendiente de facturar</span>',
                ),
            })

    puede_editar = puede_editar_cotizaciones(request.user) and cot.es_editable
    puede_enviar = puede_enviar_cotizaciones(request.user) and cot.estado == "borrador"
    puede_aprobar = puede_aprobar_cotizaciones(request.user) and cot.estado == "enviada"
    puede_rechazar = puede_rechazar_cotizaciones(request.user) and cot.estado == "enviada"
    puede_anular = puede_anular_cotizaciones(request.user) and cot.estado != "anulada"
    puede_duplicar = puede_crear_cotizaciones(request.user)

    acciones_html: list = []
    if puede_editar:
        acciones_html.append(format_html(
            '<a href="{}" class="btn-secundario">Editar</a>',
            reverse("cotizaciones:editar", args=[cot.pk]),
        ))
    if puede_enviar:
        acciones_html.append(format_html(
            '<button type="button" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML" class="btn-primario">Marcar enviada</button>',
            reverse("cotizaciones:enviar", args=[cot.pk]),
        ))
    if puede_aprobar:
        acciones_html.append(format_html(
            '<button type="button" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML" class="btn-primario">Aprobar</button>',
            reverse("cotizaciones:aprobar", args=[cot.pk]),
        ))
    if puede_rechazar:
        acciones_html.append(format_html(
            '<button type="button" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML" class="btn-secundario">Rechazar</button>',
            reverse("cotizaciones:rechazar", args=[cot.pk]),
        ))
    if puede_duplicar:
        from django.middleware.csrf import get_token
        token = get_token(request)
        acciones_html.append(format_html(
            '<form method="post" action="{}" class="inline">'
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
            '<button type="submit" class="btn-secundario">Duplicar</button></form>',
            reverse("cotizaciones:duplicar", args=[cot.pk]),
            token,
        ))
    if puede_anular:
        acciones_html.append(format_html(
            '<button type="button" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML" class="text-sm text-error-600 hover:underline">Anular</button>',
            reverse("cotizaciones:anular", args=[cot.pk]),
        ))

    # Botón "Generar factura del anticipo" — sólo si aprobada y anticipo
    # configurado pero aún no facturado.
    if cot.anticipo_pendiente and puede_crear_cotizaciones(request.user):
        from django.middleware.csrf import get_token
        token = get_token(request)
        acciones_html.append(format_html(
            '<form method="post" action="{}" class="inline">'
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
            '<button type="submit" class="btn-primario" '
            'title="Crea una Factura en borrador por el monto del anticipo, vinculada a esta cotización.">'
            'Generar factura del anticipo</button></form>',
            reverse("cotizaciones:factura-anticipo", args=[cot.pk]),
            token,
        ))

    action_bar_acciones = mark_safe("".join(str(a) for a in acciones_html))
    action_bar_meta = format_html(
        '<span class="text-gray-500">Última actualización {}</span>',
        cot.actualizado_en.strftime("%Y-%m-%d %H:%M"),
    )

    return render(request, "cotizaciones/detalle.html", {
        "cot": cot,
        "items": items,
        "totales": totales,
        "info_cliente": info_cliente,
        "info_fechas": info_fechas,
        "info_aprobacion": info_aprobacion,
        "info_anticipo": info_anticipo,
        "info_captura": info_captura,
        "action_bar_meta": action_bar_meta,
        "action_bar_acciones": action_bar_acciones,
        "puede_editar": puede_editar,
        "puede_enviar": puede_enviar,
        "puede_aprobar": puede_aprobar,
        "puede_rechazar": puede_rechazar,
        "puede_anular": puede_anular,
        "puede_duplicar": puede_duplicar,
    })


# --- Modales HTMX (patrón Wave 5) ---------------------------------------

def _modal_response(request, template: str, ctx: dict, status: int = 200):
    return render(request, template, ctx, status=status)


def _hx_redirect(url: str) -> HttpResponse:
    return HttpResponse(status=204, headers={"HX-Redirect": url})


@login_required
def enviar(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    cot = get_object_or_404(Cotizacion, pk=pk)
    if not puede_enviar_cotizaciones(request.user):
        return HttpResponseForbidden("Sin permiso para enviar cotizaciones.")
    if cot.estado != "borrador":
        messages.error(request, "Solo se puede enviar en estado borrador.")
        return redirect("cotizaciones:detalle", pk=cot.pk)

    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = EnviarForm(request.POST)
        if form.is_valid():
            services.marcar_enviada(cot, request.user, form.cleaned_data.get("email_destino", ""))
            messages.success(request, f"Cotización {cot.codigo} marcada como enviada.")
            destino = reverse("cotizaciones:detalle", args=[cot.pk])
            if es_htmx:
                return _hx_redirect(destino)
            return redirect(destino)
        if es_htmx:
            return _modal_response(request, "cotizaciones/_modal_enviar.html",
                                   {"cot": cot, "form": form})
        return render(request, "cotizaciones/_modal_enviar.html",
                      {"cot": cot, "form": form})

    form = EnviarForm(initial={"email_destino": getattr(cot.cliente, "email_contacto", "")})
    return _modal_response(request, "cotizaciones/_modal_enviar.html",
                           {"cot": cot, "form": form})


@login_required
def aprobar(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    cot = get_object_or_404(Cotizacion, pk=pk)
    if not puede_aprobar_cotizaciones(request.user):
        return HttpResponseForbidden("Sin permiso para aprobar cotizaciones.")
    if cot.estado != "enviada":
        messages.error(request, "Solo se puede aprobar una cotización enviada.")
        return redirect("cotizaciones:detalle", pk=cot.pk)
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = AprobarForm(request.POST)
        if form.is_valid():
            services.marcar_aprobada(
                cot, request.user,
                nombre=form.cleaned_data["nombre"],
                email=form.cleaned_data.get("email", ""),
                referencia=form.cleaned_data.get("referencia", ""),
            )
            messages.success(request, f"Cotización {cot.codigo} aprobada.")
            destino = reverse("cotizaciones:detalle", args=[cot.pk])
            return _hx_redirect(destino) if es_htmx else redirect(destino)
        return _modal_response(request, "cotizaciones/_modal_aprobar.html",
                               {"cot": cot, "form": form})
    return _modal_response(request, "cotizaciones/_modal_aprobar.html",
                           {"cot": cot, "form": AprobarForm()})


@login_required
def rechazar(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    cot = get_object_or_404(Cotizacion, pk=pk)
    if not puede_rechazar_cotizaciones(request.user):
        return HttpResponseForbidden("Sin permiso para rechazar cotizaciones.")
    if cot.estado != "enviada":
        messages.error(request, "Solo se puede rechazar una cotización enviada.")
        return redirect("cotizaciones:detalle", pk=cot.pk)
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = RechazarForm(request.POST)
        if form.is_valid():
            services.marcar_rechazada(cot, request.user, form.cleaned_data["motivo"])
            messages.success(request, f"Cotización {cot.codigo} rechazada.")
            destino = reverse("cotizaciones:detalle", args=[cot.pk])
            return _hx_redirect(destino) if es_htmx else redirect(destino)
        return _modal_response(request, "cotizaciones/_modal_rechazar.html",
                               {"cot": cot, "form": form})
    return _modal_response(request, "cotizaciones/_modal_rechazar.html",
                           {"cot": cot, "form": RechazarForm()})


@login_required
def anular(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    cot = get_object_or_404(Cotizacion, pk=pk)
    if not puede_anular_cotizaciones(request.user):
        return HttpResponseForbidden("Sin permiso para anular cotizaciones.")
    if cot.estado == "anulada":
        messages.error(request, "La cotización ya estaba anulada.")
        return redirect("cotizaciones:detalle", pk=cot.pk)
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = AnularForm(request.POST)
        if form.is_valid():
            services.marcar_anulada(cot, request.user, form.cleaned_data["motivo"])
            messages.success(request, f"Cotización {cot.codigo} anulada.")
            destino = reverse("cotizaciones:detalle", args=[cot.pk])
            return _hx_redirect(destino) if es_htmx else redirect(destino)
        return _modal_response(request, "cotizaciones/_modal_anular.html",
                               {"cot": cot, "form": form})
    return _modal_response(request, "cotizaciones/_modal_anular.html",
                           {"cot": cot, "form": AnularForm()})


@login_required
def duplicar(request, pk):
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_crear_cotizaciones(request.user):
        return HttpResponseForbidden("Sin permiso para crear cotizaciones.")
    if request.method != "POST":
        return HttpResponseForbidden("Método no permitido.")
    cot = get_object_or_404(Cotizacion, pk=pk)
    nueva = services.duplicar(cot, request.user)
    messages.success(request, f"Cotización duplicada como {nueva.codigo}.")
    return redirect("cotizaciones:editar", pk=nueva.pk)


@login_required
def api_proyecto_datos(request, pk):
    """Datos del proyecto para auto-llenar el form de cotización.

    GET /cotizaciones/api/proyecto/<pk>/datos/
    → {id, codigo, nombre, cliente_id, cliente_nombre}

    Gated por `puede_ver_cotizaciones` para no acoplar el form de
    Cotizaciones al permiso de Tesorería (S-LC-Feedback-V4 hotfix 2).
    """
    from apps.los_proyectos.models import Proyecto
    from django.http import JsonResponse

    if (r := _gate_ver(request)) is not None:
        return r
    proyecto = get_object_or_404(
        Proyecto.objects.select_related("cliente"), pk=pk,
    )
    return JsonResponse({
        "id": proyecto.pk,
        "codigo": proyecto.codigo,
        "nombre": proyecto.nombre,
        "cliente_id": proyecto.cliente_id,
        "cliente_nombre": proyecto.cliente.razon_social if proyecto.cliente else "",
    })


@login_required
def factura_anticipo(request, pk):
    """Genera Factura por el monto del anticipo desde una cotización
    aprobada (S-Finanzas-V2 #E). POST-only."""
    if (r := _gate_ver(request)) is not None:
        return r
    if not puede_crear_cotizaciones(request.user):
        return HttpResponseForbidden("Sin permiso.")
    if request.method != "POST":
        return HttpResponseForbidden("Método no permitido.")
    cot = get_object_or_404(Cotizacion, pk=pk)
    try:
        factura = services.crear_factura_anticipo(cot, request.user)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("cotizaciones:detalle", pk=cot.pk)
    messages.success(
        request,
        f"Factura del anticipo {factura.codigo} creada en borrador. "
        f"Revisa los datos y emítela cuando estés listo.",
    )
    return redirect("facturacion:editar", pk=factura.pk)
