"""CRUD de Tipos del Buzón desde La Gerencia (S-LC-Buzon-V2).

Solo super_admin. Los tipos `sistema=True` (sugerencia/problema/otro) no se
borran — pero sí se editan (label/color/orden/activo). Los tipos nuevos se
borran si ningún ticket los usa. Espejo de estados_buzon.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from buzon.models import MensajeBuzon, TipoBuzon
from lib.permisos import es_super_admin, puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import TipoBuzonForm, TipoBuzonNuevoForm


def _gate(request):
    u = request.user
    if not (es_super_admin(u) or puede(u, "catalogos", "tipos")):
        return HttpResponseForbidden("Sin permiso para gestionar este catálogo.")
    return None


@login_required
def lista(request):
    if (r := _gate(request)) is not None:
        return r
    uso = dict(
        MensajeBuzon.objects.values_list("tipo").annotate(n=Count("pk")).values_list("tipo", "n")
    )
    tipos = list(TipoBuzon.objects.all().order_by("orden", "label"))
    for t in tipos:
        t.tickets_usando = uso.get(t.slug, 0)
    return render(request, "tipos_buzon/lista.html", {"tipos": tipos})


@login_required
def nuevo(request):
    if (r := _gate(request)) is not None:
        return r
    if request.method == "POST":
        form = TipoBuzonNuevoForm(request.POST)
        if form.is_valid():
            obj = form.save()
            emitir(EventoPortavoz(
                tipo="buzon.tipo_creado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Tipo «{obj.label}» creado.")
            return redirect("tipos-buzon-lista")
    else:
        form = TipoBuzonNuevoForm()
    return render(request, "tipos_buzon/form.html", {"form": form, "modo": "nuevo"})


@login_required
def editar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    obj = get_object_or_404(TipoBuzon, slug=slug)
    if request.method == "POST":
        form = TipoBuzonForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="buzon.tipo_actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Tipo «{obj.label}» actualizado.")
            return redirect("tipos-buzon-lista")
    else:
        form = TipoBuzonForm(instance=obj)
    return render(request, "tipos_buzon/form.html", {"form": form, "modo": "editar", "tipo": obj})


@login_required
def toggle_activo(request, slug):
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("tipos-buzon-lista")
    obj = get_object_or_404(TipoBuzon, slug=slug)
    obj.activo = not obj.activo
    obj.save(update_fields=["activo"])
    emitir(EventoPortavoz(
        tipo="buzon.tipo_actualizado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": obj.slug, "label": obj.label, "activo": obj.activo},
    ))
    messages.success(request, f"Tipo «{obj.label}» {'mostrado' if obj.activo else 'oculto'}.")
    return redirect("tipos-buzon-lista")


@login_required
def borrar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("tipos-buzon-lista")
    obj = get_object_or_404(TipoBuzon, slug=slug)
    if obj.sistema:
        messages.error(request, "No se puede borrar un tipo del sistema. Desactívalo si no lo usas.")
        return redirect("tipos-buzon-lista")
    if MensajeBuzon.objects.filter(tipo=obj.slug).exists():
        messages.error(request, f"No se puede borrar «{obj.label}»: hay tickets usándolo. Desactívalo primero.")
        return redirect("tipos-buzon-lista")
    label = obj.label
    obj.delete()
    emitir(EventoPortavoz(
        tipo="buzon.tipo_borrado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": slug, "label": label},
    ))
    messages.success(request, f"Tipo «{label}» borrado.")
    return redirect("tipos-buzon-lista")
