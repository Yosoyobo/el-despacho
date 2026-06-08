"""CRUD de Estados del Buzón desde La Gerencia (S-Buzon-Estados-V1).

Solo super_admin. Los estados sembrados como `sistema=True` (los 4
canónicos del Buzón) NO se pueden borrar — pero sí editar
label/color/orden/terminal/activo. Los estados nuevos (`sistema=False`)
sí se pueden borrar siempre y cuando ningún ticket los use.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from buzon.models import EstadoBuzon, MensajeBuzon
from lib.permisos import es_super_admin
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import EstadoBuzonForm, EstadoBuzonNuevoForm


def _gate(request):
    if not es_super_admin(request.user):
        return HttpResponseForbidden("Solo super_admin gestiona estados.")
    return None


@login_required
def lista(request):
    if (r := _gate(request)) is not None:
        return r
    from django.db.models import Count
    uso = dict(
        MensajeBuzon.objects.values_list("estado").annotate(n=Count("pk")).values_list("estado", "n")
    )
    estados = list(EstadoBuzon.objects.all().order_by("orden", "label"))
    for e in estados:
        e.tickets_usando = uso.get(e.slug, 0)
    return render(request, "estados_buzon/lista.html", {"estados": estados})


@login_required
def nuevo(request):
    if (r := _gate(request)) is not None:
        return r
    if request.method == "POST":
        form = EstadoBuzonNuevoForm(request.POST)
        if form.is_valid():
            obj = form.save()
            emitir(EventoPortavoz(
                tipo="buzon.estado_creado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Estado «{obj.label}» creado.")
            return redirect("estados-buzon-lista")
    else:
        form = EstadoBuzonNuevoForm()
    return render(request, "estados_buzon/form.html", {"form": form, "modo": "nuevo"})


@login_required
def editar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    obj = get_object_or_404(EstadoBuzon, slug=slug)
    if request.method == "POST":
        form = EstadoBuzonForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="buzon.estado_actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Estado «{obj.label}» actualizado.")
            return redirect("estados-buzon-lista")
    else:
        form = EstadoBuzonForm(instance=obj)
    return render(request, "estados_buzon/form.html", {"form": form, "modo": "editar", "estado": obj})


@login_required
def toggle_activo(request, slug):
    """Oculta/muestra un estado del Buzón sin borrarlo. Inactivo = desaparece
    del filtro y del selector de respuesta; los tickets que ya lo usan lo
    conservan. Reversible; aplica incluso a estados en uso o del sistema."""
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("estados-buzon-lista")
    obj = get_object_or_404(EstadoBuzon, slug=slug)
    obj.activo = not obj.activo
    obj.save(update_fields=["activo"])
    emitir(EventoPortavoz(
        tipo="buzon.estado_actualizado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": obj.slug, "label": obj.label, "activo": obj.activo},
    ))
    messages.success(request, f"Estado «{obj.label}» {'mostrado' if obj.activo else 'oculto'}.")
    return redirect("estados-buzon-lista")


@login_required
def borrar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("estados-buzon-lista")
    obj = get_object_or_404(EstadoBuzon, slug=slug)
    if obj.sistema:
        messages.error(request, "No se puede borrar un estado del sistema. Desactívalo si no lo usas.")
        return redirect("estados-buzon-lista")
    if MensajeBuzon.objects.filter(estado=obj.slug).exists():
        messages.error(request, f"No se puede borrar «{obj.label}»: hay tickets usándolo. Desactívalo o reasigna primero.")
        return redirect("estados-buzon-lista")
    label = obj.label
    obj.delete()
    emitir(EventoPortavoz(
        tipo="buzon.estado_borrado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": slug, "label": label},
    ))
    messages.success(request, f"Estado «{label}» borrado.")
    return redirect("estados-buzon-lista")
