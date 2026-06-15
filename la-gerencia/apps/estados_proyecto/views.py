"""CRUD de Estados de Proyecto desde La Gerencia (S-Proyecto-Estados-V1).

Solo super_admin. Los estados sembrados como `sistema=True` (los 7
canónicos del ciclo LC) NO se pueden borrar — pero sí editar
label/color/orden/terminal/activo. Los estados nuevos (`sistema=False`)
sí se pueden borrar siempre y cuando ningún proyecto los use.
"""

from __future__ import annotations

from apps.los_proyectos.models import EstadoProyecto, Proyecto
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import es_super_admin, puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import EstadoProyectoForm, EstadoProyectoNuevoForm


def _gate(request):
    u = request.user
    if not (es_super_admin(u) or puede(u, "catalogos", "estados")):
        return HttpResponseForbidden("Sin permiso para gestionar este catálogo.")
    return None


@login_required
def lista(request):
    if (r := _gate(request)) is not None:
        return r
    # Conteo de proyectos por slug para mostrar uso.
    from django.db.models import Count
    uso = dict(
        Proyecto.objects.values_list("estado").annotate(n=Count("pk")).values_list("estado", "n")
    )
    estados = list(EstadoProyecto.objects.all().order_by("orden", "label"))
    for e in estados:
        e.proyectos_usando = uso.get(e.slug, 0)
    return render(request, "estados_proyecto/lista.html", {"estados": estados})


@login_required
def nuevo(request):
    if (r := _gate(request)) is not None:
        return r
    if request.method == "POST":
        form = EstadoProyectoNuevoForm(request.POST)
        if form.is_valid():
            obj = form.save()
            emitir(EventoPortavoz(
                tipo="proyecto.estado_creado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Estado «{obj.label}» creado.")
            return redirect("estados-proyecto-lista")
    else:
        form = EstadoProyectoNuevoForm()
    return render(request, "estados_proyecto/form.html", {"form": form, "modo": "nuevo"})


@login_required
def editar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    obj = get_object_or_404(EstadoProyecto, slug=slug)
    if request.method == "POST":
        form = EstadoProyectoForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="proyecto.estado_actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"slug": obj.slug, "label": obj.label},
            ))
            messages.success(request, f"Estado «{obj.label}» actualizado.")
            return redirect("estados-proyecto-lista")
    else:
        form = EstadoProyectoForm(instance=obj)
    return render(request, "estados_proyecto/form.html", {"form": form, "modo": "editar", "estado": obj})


@login_required
def toggle_activo(request, slug):
    """Oculta/muestra un estado sin borrarlo. Un estado inactivo desaparece del
    dropdown del detalle del proyecto; los proyectos que ya lo usan lo conservan.
    Sirve para 'desaparecer' estados que ya no se usan, incluso si están en uso
    o son del sistema (es reversible)."""
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("estados-proyecto-lista")
    obj = get_object_or_404(EstadoProyecto, slug=slug)
    obj.activo = not obj.activo
    obj.save(update_fields=["activo"])
    emitir(EventoPortavoz(
        tipo="proyecto.estado_actualizado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": obj.slug, "label": obj.label, "activo": obj.activo},
    ))
    messages.success(request, f"Estado «{obj.label}» {'mostrado' if obj.activo else 'oculto'}.")
    return redirect("estados-proyecto-lista")


@login_required
def borrar(request, slug):
    if (r := _gate(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("estados-proyecto-lista")
    obj = get_object_or_404(EstadoProyecto, slug=slug)
    if obj.sistema:
        messages.error(request, "No se puede borrar un estado del sistema. Desactívalo si no lo usas.")
        return redirect("estados-proyecto-lista")
    if Proyecto.objects.filter(estado=obj.slug).exists():
        messages.error(request, f"No se puede borrar «{obj.label}»: hay proyectos usándolo. Desactívalo o reasigna primero.")
        return redirect("estados-proyecto-lista")
    label = obj.label
    obj.delete()
    emitir(EventoPortavoz(
        tipo="proyecto.estado_borrado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"slug": slug, "label": label},
    ))
    messages.success(request, f"Estado «{label}» borrado.")
    return redirect("estados-proyecto-lista")
