"""CRUD de Estados de Cotización desde La Gerencia.

Mismo patrón que Estados de proyecto / Estados de tarea. El recuadro
«Cotizaciones» del detalle de proyecto (El Taller) pinta el pizza-tracker con
estos pasos. Solo super_admin (o permiso catalogos/estados). Los 4 base
(sistema=True) NO se borran — pero sí renombrar/recolorear/reordenar.
"""

from __future__ import annotations

from apps.cotizaciones.models import Cotizacion, EstadoCotizacion
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import es_super_admin, puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import EstadoCotizacionForm, EstadoCotizacionNuevoForm


def _gate(request):
    u = request.user
    if not (es_super_admin(u) or puede(u, "catalogos", "estados")):
        return HttpResponseForbidden("Sin permiso para gestionar este catálogo.")
    return None


def _uso():
    """Conteo de cotizaciones de proyecto (version>0) por slug de estado."""
    from django.db.models import Count
    return dict(
        Cotizacion.objects.filter(version__gt=0)
        .values_list("estado")
        .annotate(n=Count("pk"))
        .values_list("estado", "n")
    )


@login_required
def lista(request):
    if (r := _gate(request)) is not None:
        return r
    uso = _uso()
    estados = list(EstadoCotizacion.objects.all().order_by("orden", "label"))
    for e in estados:
        e.cotizaciones_usando = uso.get(e.slug, 0)
    return render(request, "estados_cotizacion/lista.html", {"estados": estados})


@login_required
def nuevo(request):
    if (r := _gate(request)) is not None:
        return r
    if request.method == "POST":
        form = EstadoCotizacionNuevoForm(request.POST)
        if form.is_valid():
            obj = form.save()
            emitir(EventoPortavoz(
                tipo="cotizacion.estado_creado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Estado «{obj.label}» creado.")
            return redirect("estados-cotizacion-lista")
    else:
        form = EstadoCotizacionNuevoForm()
    return render(request, "estados_cotizacion/form.html", {"form": form, "modo": "nuevo"})


@login_required
def editar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    obj = get_object_or_404(EstadoCotizacion, slug=slug)
    if request.method == "POST":
        form = EstadoCotizacionForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="cotizacion.estado_actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Estado «{obj.label}» actualizado.")
            return redirect("estados-cotizacion-lista")
    else:
        form = EstadoCotizacionForm(instance=obj)
    return render(request, "estados_cotizacion/form.html", {"form": form, "modo": "editar", "estado": obj})


@login_required
def toggle_activo(request, slug):
    """Oculta/muestra un paso sin borrarlo. Inactivo = desaparece del recuadro
    de Cotizaciones; las cotizaciones que ya lo usan lo conservan."""
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("estados-cotizacion-lista")
    obj = get_object_or_404(EstadoCotizacion, slug=slug)
    obj.activo = not obj.activo
    obj.save(update_fields=["activo"])
    emitir(EventoPortavoz(
        tipo="cotizacion.estado_actualizado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": obj.slug, "label": obj.label, "activo": obj.activo},
    ))
    messages.success(request, f"Estado «{obj.label}» {'mostrado' if obj.activo else 'oculto'}.")
    return redirect("estados-cotizacion-lista")


@login_required
def borrar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("estados-cotizacion-lista")
    obj = get_object_or_404(EstadoCotizacion, slug=slug)
    if obj.sistema:
        messages.error(request, "No se puede borrar un estado del sistema. Desactívalo si no lo usas.")
        return redirect("estados-cotizacion-lista")
    if Cotizacion.objects.filter(estado=obj.slug, version__gt=0).exists():
        messages.error(request, f"No se puede borrar «{obj.label}»: hay cotizaciones usándolo. Desactívalo primero.")
        return redirect("estados-cotizacion-lista")
    label = obj.label
    obj.delete()
    emitir(EventoPortavoz(
        tipo="cotizacion.estado_borrado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": slug, "label": label},
    ))
    messages.success(request, f"Estado «{label}» borrado.")
    return redirect("estados-cotizacion-lista")
