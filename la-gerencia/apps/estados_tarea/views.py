"""CRUD de Estados de Tarea desde La Gerencia (S-LC-Feedback-V6 Bloque 1).

Espejo del CRUD de Estados de Proyecto. Solo super_admin. Los estados
sembrados como `sistema=True` NO se pueden borrar — pero sí editar
label/color/orden/terminal/activo. Los nuevos (`sistema=False`) sí, siempre
que ninguna tarea los use. "Atrasada" no aparece aquí: es derivada
(compromiso vencido), no un estado almacenado.
"""

from __future__ import annotations

from apps.el_pizarron.models import EstadoTarea, Tarea
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import es_super_admin, puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import EstadoTareaForm, EstadoTareaNuevoForm


def _gate(request):
    u = request.user
    if not (es_super_admin(u) or puede(u, "catalogos", "estados")):
        return HttpResponseForbidden("Sin permiso para gestionar este catálogo.")
    return None


@login_required
def lista(request):
    if (r := _gate(request)) is not None:
        return r
    from django.db.models import Count
    uso = dict(
        Tarea.objects.values_list("estado").annotate(n=Count("pk")).values_list("estado", "n")
    )
    estados = list(EstadoTarea.objects.all().order_by("orden", "label"))
    for e in estados:
        e.tareas_usando = uso.get(e.slug, 0)
    return render(request, "estados_tarea/lista.html", {"estados": estados})


@login_required
def nuevo(request):
    if (r := _gate(request)) is not None:
        return r
    if request.method == "POST":
        form = EstadoTareaNuevoForm(request.POST)
        if form.is_valid():
            obj = form.save()
            emitir(EventoPortavoz(
                tipo="tarea.estado_creado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Estado «{obj.label}» creado.")
            return redirect("estados-tarea-lista")
    else:
        form = EstadoTareaNuevoForm()
    return render(request, "estados_tarea/form.html", {"form": form, "modo": "nuevo"})


@login_required
def editar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    obj = get_object_or_404(EstadoTarea, slug=slug)
    if request.method == "POST":
        form = EstadoTareaForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="tarea.estado_actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Estado «{obj.label}» actualizado.")
            return redirect("estados-tarea-lista")
    else:
        form = EstadoTareaForm(instance=obj)
    return render(request, "estados_tarea/form.html", {"form": form, "modo": "editar", "estado": obj})


@login_required
def toggle_activo(request, slug):
    """Oculta/muestra un estado sin borrarlo. Las tareas que ya lo usan lo
    conservan; solo desaparece de los dropdowns."""
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("estados-tarea-lista")
    obj = get_object_or_404(EstadoTarea, slug=slug)
    obj.activo = not obj.activo
    obj.save(update_fields=["activo"])
    emitir(EventoPortavoz(
        tipo="tarea.estado_actualizado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": obj.slug, "label": obj.label, "activo": obj.activo},
    ))
    messages.success(request, f"Estado «{obj.label}» {'mostrado' if obj.activo else 'oculto'}.")
    return redirect("estados-tarea-lista")


@login_required
def borrar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("estados-tarea-lista")
    obj = get_object_or_404(EstadoTarea, slug=slug)
    if obj.sistema:
        messages.error(request, "No se puede borrar un estado del sistema. Desactívalo si no lo usas.")
        return redirect("estados-tarea-lista")
    if Tarea.objects.filter(estado=obj.slug).exists():
        messages.error(request, f"No se puede borrar «{obj.label}»: hay tareas usándolo. Desactívalo o reasigna primero.")
        return redirect("estados-tarea-lista")
    label = obj.label
    obj.delete()
    emitir(EventoPortavoz(
        tipo="tarea.estado_borrado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": slug, "label": label},
    ))
    messages.success(request, f"Estado «{label}» borrado.")
    return redirect("estados-tarea-lista")
