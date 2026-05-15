from apps.el_pizarron.forms import ComentarioForm, TareaForm
from apps.el_pizarron.models import Tarea
from apps.los_proyectos.models import Proyecto
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from lib.permisos import (
    es_admin,
    puede_ver_comentario,
    puede_ver_proyecto,
    puede_ver_tarea,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz
from lib.sanear import sanear_contexto


def _comentarios_visibles(user, queryset):
    return [c for c in queryset if puede_ver_comentario(user, c)]


@login_required
def nueva_tarea(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden()
    if request.method == "POST":
        form = TareaForm(request.POST)
        if form.is_valid():
            tarea = form.save(commit=False)
            tarea.proyecto = proyecto
            tarea.creado_por = request.user
            tarea.save()
            emitir(EventoPortavoz(
                tipo="tarea.creada",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"tarea_id": tarea.pk, "proyecto_id": proyecto.pk},
            ))
            messages.success(request, "Tarea creada.")
            return redirect("pizarron-detalle-tarea", pk=tarea.pk)
    else:
        form = TareaForm()
    return render(request, "pizarron/form_tarea.html", {"form": form, "proyecto": proyecto, "modo": "nueva"})


@login_required
def detalle_tarea(request, pk):
    tarea = get_object_or_404(Tarea.objects.select_related("proyecto", "asignada_a"), pk=pk)
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    comentarios = _comentarios_visibles(
        request.user,
        tarea.comentarios.select_related("autor"),
    )
    return render(request, "pizarron/detalle_tarea.html", {
        "tarea": tarea,
        "proyecto": tarea.proyecto,
        "comentarios": comentarios,
        "puede_editar": puede_ver_proyecto(request.user, tarea.proyecto),
        "es_admin": es_admin(request.user),
    })


@login_required
def editar_tarea(request, pk):
    tarea = get_object_or_404(Tarea, pk=pk)
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    if request.method == "POST":
        form = TareaForm(request.POST, instance=tarea)
        if form.is_valid():
            form.save()
            messages.success(request, "Tarea actualizada.")
            return redirect("pizarron-detalle-tarea", pk=tarea.pk)
    else:
        form = TareaForm(instance=tarea)
    return render(request, "pizarron/form_tarea.html", {"form": form, "tarea": tarea, "proyecto": tarea.proyecto, "modo": "editar"})


@login_required
def completar_tarea(request, pk):
    if request.method != "POST":
        return redirect("pizarron-detalle-tarea", pk=pk)
    tarea = get_object_or_404(Tarea, pk=pk)
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    tarea.estado = "completada"
    tarea.completada_en = timezone.now()
    tarea.save(update_fields=["estado", "completada_en"])
    emitir(EventoPortavoz(
        tipo="tarea.completada",
        actor_id=request.user.pk,
        actor_email=request.user.email,
        payload={"tarea_id": tarea.pk, "proyecto_id": tarea.proyecto_id},
    ))
    messages.success(request, "Tarea completada.")
    return redirect("pizarron-detalle-tarea", pk=tarea.pk)


@login_required
def comentar_tarea(request, pk):
    tarea = get_object_or_404(Tarea, pk=pk)
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    if request.method != "POST":
        return redirect("pizarron-detalle-tarea", pk=pk)
    form = ComentarioForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.tarea = tarea
        c.autor = request.user
        c.cuerpo = sanear_contexto(c.cuerpo)
        # Diseñadores no pueden marcar comentarios como internos (privilegio admin/contador).
        if not es_admin(request.user) and getattr(request.user, "rol", None) != "contador":
            c.es_interno = False
        c.save()
        messages.success(request, "Comentario agregado.")
    else:
        messages.error(request, "Comentario inválido.")
    return redirect("pizarron-detalle-tarea", pk=tarea.pk)


@login_required
def comentar_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden()
    if request.method != "POST":
        return redirect("proyectos-detalle", pk=proyecto.pk)
    form = ComentarioForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.proyecto = proyecto
        c.autor = request.user
        c.cuerpo = sanear_contexto(c.cuerpo)
        if not es_admin(request.user) and getattr(request.user, "rol", None) != "contador":
            c.es_interno = False
        c.save()
        messages.success(request, "Comentario agregado al proyecto.")
    return redirect("proyectos-detalle", pk=proyecto.pk)
