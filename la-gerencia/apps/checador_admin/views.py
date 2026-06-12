"""El Checador desde La Gerencia (E5): CRUD de horarios + bandeja de correcciones.

Los modelos viven en El Taller (apps.checador); Gerencia los administra.
Horarios → gated por `configurar_horarios`. Correcciones → `aprobar_correcciones`.
"""

from __future__ import annotations

from apps.checador import services
from apps.checador.models import HorarioLaboral, SolicitudCorreccion
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import (
    puede_aprobar_correcciones_checador,
    puede_configurar_horarios_checador,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import HorarioLaboralForm


def _gate_horarios(request):
    if not puede_configurar_horarios_checador(request.user):
        return HttpResponseForbidden("Sin permiso para configurar horarios.")
    return None


def _gate_correcciones(request):
    if not puede_aprobar_correcciones_checador(request.user):
        return HttpResponseForbidden("Sin permiso para aprobar correcciones.")
    return None


# ───────────────────────── horarios ─────────────────────────

@login_required
def horarios(request):
    if (r := _gate_horarios(request)) is not None:
        return r
    globales = list(HorarioLaboral.objects.filter(usuario__isnull=True).order_by("dia_semana"))
    overrides = list(
        HorarioLaboral.objects.filter(usuario__isnull=False)
        .select_related("usuario").order_by("usuario__nombre_completo", "dia_semana"),
    )
    return render(request, "checador_admin/horarios.html", {
        "globales": globales, "overrides": overrides,
    })


@login_required
def horario_nuevo(request):
    if (r := _gate_horarios(request)) is not None:
        return r
    if request.method == "POST":
        form = HorarioLaboralForm(request.POST)
        if form.is_valid():
            obj = form.save()
            _emit_horario(request, obj, "creado")
            messages.success(request, "Horario creado.")
            return redirect("checador-admin-horarios")
    else:
        form = HorarioLaboralForm()
    return render(request, "checador_admin/horario_form.html", {"form": form, "modo": "nuevo"})


@login_required
def horario_editar(request, pk):
    if (r := _gate_horarios(request)) is not None:
        return r
    obj = get_object_or_404(HorarioLaboral, pk=pk)
    if request.method == "POST":
        form = HorarioLaboralForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            _emit_horario(request, obj, "actualizado")
            messages.success(request, "Horario actualizado.")
            return redirect("checador-admin-horarios")
    else:
        form = HorarioLaboralForm(instance=obj)
    return render(request, "checador_admin/horario_form.html", {"form": form, "modo": "editar", "obj": obj})


@login_required
def horario_borrar(request, pk):
    if (r := _gate_horarios(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("checador-admin-horarios")
    obj = get_object_or_404(HorarioLaboral, pk=pk)
    if obj.usuario_id is None:
        messages.error(request, "No se puede borrar un horario global. Desactívalo si no aplica.")
        return redirect("checador-admin-horarios")
    obj.delete()
    _emit_horario(request, obj, "borrado")
    messages.success(request, "Horario eliminado.")
    return redirect("checador-admin-horarios")


def _emit_horario(request, obj, accion):
    emitir(EventoPortavoz(
        tipo="checador.horario_actualizado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"horario_id": obj.pk, "usuario_id": obj.usuario_id, "dia": obj.dia_semana, "accion": accion},
    ))


# ───────────────────────── correcciones (bandeja espejo) ─────────────────────────

@login_required
def correcciones(request):
    if (r := _gate_correcciones(request)) is not None:
        return r
    pendientes = list(
        SolicitudCorreccion.objects.filter(estado="pendiente")
        .select_related("usuario", "jornada", "sesion").order_by("creado_en"),
    )
    resueltas = list(
        SolicitudCorreccion.objects.exclude(estado="pendiente")
        .select_related("usuario", "resuelto_por").order_by("-resuelto_en")[:20],
    )
    return render(request, "checador_admin/correcciones.html", {
        "pendientes": pendientes, "resueltas": resueltas,
    })


@login_required
def correccion_resolver_modal(request, pk):
    if (r := _gate_correcciones(request)) is not None:
        return r
    sol = get_object_or_404(SolicitudCorreccion, pk=pk)
    return render(request, "checador_admin/_modal_resolver.html", {"sol": sol})


@login_required
def correccion_resolver(request, pk):
    if (r := _gate_correcciones(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("checador-admin-correcciones")
    sol = get_object_or_404(SolicitudCorreccion, pk=pk)
    aprobar = request.POST.get("decision") == "aprobar"
    comentario = (request.POST.get("comentario") or "").strip()
    try:
        services.resolver_correccion(sol, admin=request.user, aprobar=aprobar, comentario=comentario)
        messages.success(request, "Corrección aprobada." if aprobar else "Corrección rechazada.")
    except ValueError as exc:
        messages.error(request, str(exc))
    if request.headers.get("HX-Request") == "true":
        from django.urls import reverse
        return HttpResponse(status=204, headers={"HX-Redirect": reverse("checador-admin-correcciones")})
    return redirect("checador-admin-correcciones")
