"""Compras: las órdenes de compra a proveedores (2026-09-29).

Permisos (§4 #20, módulo `compras`): `ver` la lista y el documento, `crear`,
`editar` (también marcarla enviada o recibida) y `cancelar`. El documento en PDF
lo arma La Imprenta (`/documentos/orden_compra/<pk>/`).
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from lib import edicion
from lib.permisos import (
    puede_cancelar_compras,
    puede_crear_compras,
    puede_editar_compras,
    puede_ver_compras,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import ItemFormSet, OrdenCompraForm
from .models import ESTADOS_ORDEN, OrdenCompra


def _emitir(tipo: str, orden: OrdenCompra, usuario, extra: dict | None = None) -> None:
    emitir(EventoPortavoz(
        tipo=tipo, actor_id=usuario.pk, actor_email=usuario.email,
        payload={"orden_id": orden.pk, "codigo": orden.codigo, "estado": orden.estado,
                 "proveedor_id": orden.proveedor_id, **(extra or {})},
    ))


def _guardar_renglones(formset) -> None:
    """Guarda los renglones en el orden de la pantalla (los vacíos no se guardan)."""
    formset.save(commit=False)
    for obj in formset.deleted_objects:
        obj.delete()
    vivos = [f for f in formset.forms if f.has_changed() or f.instance.pk]
    n = 0
    for f in vivos:
        if f in formset.deleted_forms or not f.cleaned_data:
            continue
        item = f.save(commit=False)
        item.orden_compra = formset.instance
        item.orden = n
        item.save()
        n += 1


def _migas(*extra):
    return [{"url": "/compras/", "label": "Compras"}, *extra]


@login_required
def lista(request):
    if not puede_ver_compras(request.user):
        return HttpResponseForbidden("Sin permiso para ver las compras.")
    qs = OrdenCompra.objects.select_related("proveedor", "proyecto").prefetch_related("items")
    estado = (request.GET.get("estado") or "").strip()
    if estado in {e for e, _ in ESTADOS_ORDEN}:
        qs = qs.filter(estado=estado)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(proveedor__razon_social__icontains=q)
                       | Q(proyecto__nombre__icontains=q) | Q(items__descripcion__icontains=q)).distinct()
    return render(request, "compras/lista.html", {
        "ordenes": list(qs[:200]), "estados": ESTADOS_ORDEN, "estado": estado, "q": q,
        "puede_crear": puede_crear_compras(request.user),
        "breadcrumb_items": _migas({"label": "Órdenes de compra"}),
    })


@login_required
def nueva(request):
    if not puede_crear_compras(request.user):
        return HttpResponseForbidden("Sin permiso para crear órdenes de compra.")
    if request.method == "POST":
        form = OrdenCompraForm(request.POST)
        formset = ItemFormSet(request.POST, prefix="items")
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                orden = form.save(commit=False)
                orden.creado_por = request.user
                orden.save()
                formset.instance = orden
                _guardar_renglones(formset)
            _emitir("compras.orden_creada", orden, request.user)
            messages.success(request, f"Orden {orden.codigo} creada.")
            return redirect("compras:detalle", pk=orden.pk)
    else:
        inicial = {}
        if (p := request.GET.get("proyecto", "")).isdigit():
            inicial["proyecto"] = int(p)
        if (pv := request.GET.get("proveedor", "")).isdigit():
            inicial["proveedor"] = int(pv)
        form = OrdenCompraForm(initial=inicial)
        formset = ItemFormSet(prefix="items")
    return render(request, "compras/form.html", {
        "form": form, "formset": formset, "modo": "nueva",
        "breadcrumb_items": _migas({"label": "Nueva orden"}),
    })


@login_required
def detalle(request, pk):
    if not puede_ver_compras(request.user):
        return HttpResponseForbidden("Sin permiso para ver las compras.")
    orden = get_object_or_404(OrdenCompra.objects.select_related("proveedor", "proyecto"), pk=pk)
    return render(request, "compras/detalle.html", {
        "orden": orden, "items": list(orden.items.all()),
        "puede_editar": puede_editar_compras(request.user) and orden.es_editable,
        "puede_cancelar": puede_cancelar_compras(request.user) and orden.estado != "cancelada",
        "breadcrumb_items": _migas({"label": orden.codigo}),
    })


def _edicion_orden(orden, form, formset):
    """Lo que vigila El Testigo: los datos de la orden y sus renglones."""
    return edicion.Edicion(orden, form, grupos={"items": edicion.Grupo(
        formset, etiqueta_linea=lambda it: f"el renglón «{it.descripcion or 'sin descripción'}»")})


@login_required
def editar(request, pk):
    if not puede_editar_compras(request.user):
        return HttpResponseForbidden("Sin permiso para editar órdenes de compra.")
    orden = get_object_or_404(OrdenCompra, pk=pk)
    if not orden.es_editable:
        messages.error(request, "Una orden recibida o cancelada ya no se edita.")
        return redirect("compras:detalle", pk=orden.pk)
    choque = None
    if request.method == "POST":
        form = OrdenCompraForm(request.POST, instance=orden)
        formset = ItemFormSet(request.POST, instance=orden, prefix="items")
        ed = _edicion_orden(orden, form, formset)
        # Antes de validar (§14 Bug D): ¿guardar pisaría lo que alguien más cambió?
        choque = ed.revisar(request)
        if choque is None and form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                _guardar_renglones(formset)
            edicion.firmar(orden, request.user, edicion.ventana_posteada(request))
            _emitir("compras.orden_actualizada", orden, request.user)
            messages.success(request, "Orden actualizada.")
            return redirect("compras:detalle", pk=orden.pk)
        ctx_edicion = edicion.contexto(
            request, testigo=choque.testigo if choque else ed.testigo_para(request), choque=choque)
    else:
        form = OrdenCompraForm(instance=orden)
        formset = ItemFormSet(instance=orden, prefix="items")
        ctx_edicion = edicion.contexto(request, testigo=_edicion_orden(orden, form, formset).testigo())
    return render(request, "compras/form.html", {
        "form": form, "formset": formset, "modo": "editar", "orden": orden, "edicion": ctx_edicion,
        "breadcrumb_items": _migas({"url": f"/compras/{orden.pk}/", "label": orden.codigo},
                                   {"label": "Editar"}),
    }, status=409 if choque else 200)


@login_required
@require_POST
def estado(request, pk):
    """Enviada / recibida (quien edita) o cancelada (quien cancela)."""
    orden = get_object_or_404(OrdenCompra, pk=pk)
    nuevo = (request.POST.get("estado") or "").strip()
    ahora = timezone.now()
    if nuevo == "cancelada":
        if not puede_cancelar_compras(request.user):
            return HttpResponseForbidden("Sin permiso para cancelar órdenes de compra.")
        orden.estado, orden.cancelada_en = "cancelada", ahora
    elif nuevo in ("enviada", "recibida"):
        if not puede_editar_compras(request.user):
            return HttpResponseForbidden("Sin permiso para cambiar órdenes de compra.")
        if orden.estado == "cancelada":
            messages.error(request, "La orden está cancelada.")
            return redirect("compras:detalle", pk=orden.pk)
        orden.estado = nuevo
        if nuevo == "enviada":
            orden.enviada_en = ahora
        else:
            orden.recibida_en = ahora
    else:
        messages.error(request, "Estado inválido.")
        return redirect("compras:detalle", pk=orden.pk)
    orden.save()
    _emitir("compras.orden_estado", orden, request.user)
    messages.success(request, f"Orden {orden.codigo}: {orden.get_estado_display().lower()}.")
    return redirect("compras:detalle", pk=orden.pk)
