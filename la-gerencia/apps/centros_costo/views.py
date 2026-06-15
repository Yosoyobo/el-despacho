"""CRUD de centros de costo en La Gerencia → Catálogos.

Solo super_admin. La tabla Django vive en la app `tesoreria` de El Taller;
La Gerencia la consume sin volverla a definir. Patrón identical al de
otros catálogos cross-app que comparten DB Postgres."""

from __future__ import annotations

from apps.tesoreria.models import CentroDeCosto
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import es_super_admin, puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import CentroDeCostoForm


def _gate(request):
    u = request.user
    if not (es_super_admin(u) or puede(u, "catalogos", "centros_costo")):
        return HttpResponseForbidden("Sin permiso para gestionar este catálogo.")
    return None


@login_required
def lista(request):
    if (r := _gate(request)) is not None:
        return r
    centros = CentroDeCosto.objects.all().order_by("-activo", "nombre")
    return render(request, "centros_costo/lista.html", {
        "centros": centros,
        "cabeceras_centros": [
            {"label": "Nombre"},
            {"label": "Naturaleza"},
            {"label": "Descripción"},
            {"label": "Estado"},
            {"label": "", "align": "right"},
        ],
    })


@login_required
def nuevo(request):
    if (r := _gate(request)) is not None:
        return r
    if request.method == "POST":
        form = CentroDeCostoForm(request.POST)
        if form.is_valid():
            centro = form.save(commit=False)
            centro.creado_por = request.user
            centro.save()
            emitir(EventoPortavoz(
                tipo="centro_costo.creado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": centro.slug, "nombre": centro.nombre},
            ))
            messages.success(request, f"Centro «{centro.nombre}» creado.")
            return redirect("centros-costo-lista")
    else:
        form = CentroDeCostoForm()
    return render(request, "centros_costo/form.html", {"form": form, "modo": "nuevo"})


@login_required
def editar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    centro = get_object_or_404(CentroDeCosto, slug=slug)
    if request.method == "POST":
        form = CentroDeCostoForm(request.POST, instance=centro)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="centro_costo.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": centro.slug},
            ))
            messages.success(request, "Centro actualizado.")
            return redirect("centros-costo-lista")
    else:
        form = CentroDeCostoForm(instance=centro)
    return render(request, "centros_costo/form.html",
                  {"form": form, "modo": "editar", "centro": centro})


@login_required
def toggle_activo(request, slug):
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("centros-costo-lista")
    centro = get_object_or_404(CentroDeCosto, slug=slug)
    centro.activo = not centro.activo
    centro.save(update_fields=["activo", "actualizado_en"])
    messages.success(request, ("Activado" if centro.activo else "Desactivado") + ".")
    return redirect("centros-costo-lista")
