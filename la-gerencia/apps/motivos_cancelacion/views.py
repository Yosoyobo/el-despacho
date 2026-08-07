"""CRUD de Motivos de cancelación desde La Gerencia (LC 2026-08-07, Oscar).

Son las pastillas que salen al cancelar un proyecto en El Taller. Oscar pidió
poder cambiar esas etiquetas «en algún lado fácil», y eligió que vivieran junto a
los demás catálogos configurables (Estados de proyecto, de tarea, de cotización).

Mismo contrato que esas pantallas: los sembrados (`sistema=True`) se renombran y
se apagan pero no se borran; los que agregue LC se borran mientras ningún
proyecto los use.
"""

from __future__ import annotations

from apps.los_proyectos.models import MotivoCancelacion, Proyecto
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import es_super_admin, puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import MotivoCancelacionForm, MotivoCancelacionNuevoForm


def _gate(request):
    u = request.user
    if not (es_super_admin(u) or puede(u, "catalogos", "estados")):
        return HttpResponseForbidden("Sin permiso para gestionar este catálogo.")
    return None


@login_required
def lista(request):
    if (r := _gate(request)) is not None:
        return r
    uso = dict(
        Proyecto.objects.filter(motivo_cancelacion__isnull=False)
        .values_list("motivo_cancelacion")
        .annotate(n=Count("pk"))
        .values_list("motivo_cancelacion", "n")
    )
    motivos = list(MotivoCancelacion.objects.all())
    for m in motivos:
        m.proyectos_usando = uso.get(m.pk, 0)
    return render(request, "motivos_cancelacion/lista.html", {"motivos": motivos})


@login_required
def nuevo(request):
    if (r := _gate(request)) is not None:
        return r
    if request.method == "POST":
        form = MotivoCancelacionNuevoForm(request.POST)
        if form.is_valid():
            obj = form.save()
            emitir(EventoPortavoz(
                tipo="proyecto.motivo_cancelacion_creado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Motivo «{obj.label}» creado.")
            return redirect("motivos-cancelacion-lista")
    else:
        form = MotivoCancelacionNuevoForm()
    return render(request, "motivos_cancelacion/form.html", {"form": form, "modo": "nuevo"})


@login_required
def editar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    obj = get_object_or_404(MotivoCancelacion, slug=slug)
    if request.method == "POST":
        form = MotivoCancelacionForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="proyecto.motivo_cancelacion_actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Motivo «{obj.label}» actualizado.")
            return redirect("motivos-cancelacion-lista")
    else:
        form = MotivoCancelacionForm(instance=obj)
    return render(request, "motivos_cancelacion/form.html",
                  {"form": form, "modo": "editar", "motivo": obj})


@login_required
def toggle_activo(request, slug):
    """Deja de ofrecerlo al cancelar sin borrarlo: los proyectos que ya lo
    tienen lo conservan y las estadísticas lo siguen contando."""
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("motivos-cancelacion-lista")
    obj = get_object_or_404(MotivoCancelacion, slug=slug)
    obj.activo = not obj.activo
    obj.save(update_fields=["activo"])
    emitir(EventoPortavoz(
        tipo="proyecto.motivo_cancelacion_actualizado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": obj.slug, "label": obj.label, "activo": obj.activo},
    ))
    messages.success(request, f"Motivo «{obj.label}» {'mostrado' if obj.activo else 'oculto'}.")
    return redirect("motivos-cancelacion-lista")


@login_required
def borrar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("motivos-cancelacion-lista")
    obj = get_object_or_404(MotivoCancelacion, slug=slug)
    if obj.sistema:
        messages.error(request, "No se puede borrar un motivo del sistema. Ocúltalo si no lo usas.")
        return redirect("motivos-cancelacion-lista")
    if Proyecto.objects.filter(motivo_cancelacion=obj).exists():
        messages.error(
            request,
            f"No se puede borrar «{obj.label}»: hay proyectos cancelados con ese motivo. Ocúltalo.")
        return redirect("motivos-cancelacion-lista")
    label = obj.label
    obj.delete()
    emitir(EventoPortavoz(
        tipo="proyecto.motivo_cancelacion_borrado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": slug, "label": label},
    ))
    messages.success(request, f"Motivo «{label}» borrado.")
    return redirect("motivos-cancelacion-lista")
