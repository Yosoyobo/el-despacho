from apps.los_proyectos.forms import AsignacionForm, CambiarEstadoForm, ProyectoForm
from apps.los_proyectos.models import ESTADOS_PROYECTO, Proyecto, ProyectoAsignacion
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import (
    es_admin,
    puede_editar_proyecto,
    puede_ver_proyecto,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


def _proyectos_visibles(user):
    """Queryset filtrado por rol."""
    rol = getattr(user, "rol", None)
    qs = Proyecto.objects.select_related("cliente")
    if rol in ("super_admin", "dueno", "contador"):
        return qs
    if rol == "disenador":
        return qs.filter(asignaciones__usuario=user).distinct()
    return Proyecto.objects.none()


@login_required
def lista(request):
    q = (request.GET.get("q") or "").strip()
    estado = request.GET.get("estado") or ""
    qs = _proyectos_visibles(request.user)
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(codigo__icontains=q) | Q(cliente__razon_social__icontains=q))
    if estado:
        qs = qs.filter(estado=estado)
    base = _proyectos_visibles(request.user)
    kpis = {
        "prospectos": base.filter(estado="prospecto").count(),
        "activos": base.filter(estado__in=("en_diseno", "revision_cliente", "en_produccion")).count(),
        "pausa": base.filter(estado="en_pausa").count(),
        "entregados": base.filter(estado="entregado").count(),
    }
    return render(request, "proyectos/lista.html", {
        "proyectos": qs,
        "q": q,
        "estado": estado,
        "estados_disponibles": ESTADOS_PROYECTO,
        "puede_crear": puede_editar_proyecto(request.user, None),
        "es_admin": es_admin(request.user),
        "kpis": kpis,
    })


@login_required
def detalle(request, pk):
    proyecto = get_object_or_404(Proyecto.objects.select_related("cliente"), pk=pk)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin acceso a este proyecto.")
    puede_ed = puede_editar_proyecto(request.user, proyecto)
    acciones_proyecto = []
    if puede_ed:
        acciones_proyecto = [
            {"url": f"/proyectos/{proyecto.pk}/editar/", "label": "Editar datos"},
            {"url": f"/proyectos/{proyecto.pk}/cambiar-estado/", "label": "Cambiar estado"},
        ]
    return render(request, "proyectos/detalle.html", {
        "proyecto": proyecto,
        "asignaciones": proyecto.asignaciones.select_related("usuario"),
        "tareas": proyecto.tareas.select_related("asignada_a").order_by("estado", "-creado_en"),
        "puede_editar": puede_ed,
        "acciones_proyecto": acciones_proyecto,
    })


@login_required
def nuevo(request):
    if not puede_editar_proyecto(request.user, None):
        return HttpResponseForbidden("Solo admins pueden crear proyectos.")
    if request.method == "POST":
        form = ProyectoForm(request.POST)
        if form.is_valid():
            proyecto = form.save(commit=False)
            proyecto.creado_por = request.user
            proyecto.save()
            emitir(EventoPortavoz(
                tipo="proyecto.creado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"proyecto_id": proyecto.pk, "codigo": proyecto.codigo, "cliente_id": proyecto.cliente_id, "estado": proyecto.estado},
            ))
            from apps.taller_home.push_handlers import notificar_proyecto_creado
            notificar_proyecto_creado(proyecto, request.user)
            messages.success(request, f"Proyecto {proyecto.codigo} creado.")
            return redirect("proyectos-detalle", pk=proyecto.pk)
    else:
        form = ProyectoForm()
    return render(request, "proyectos/form.html", {"form": form, "modo": "nuevo"})


@login_required
def editar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Solo admins pueden editar proyectos.")
    if request.method == "POST":
        form = ProyectoForm(request.POST, instance=proyecto)
        if form.is_valid():
            form.save()
            messages.success(request, "Proyecto actualizado.")
            return redirect("proyectos-detalle", pk=proyecto.pk)
    else:
        form = ProyectoForm(instance=proyecto)
    return render(request, "proyectos/form.html", {"form": form, "modo": "editar", "proyecto": proyecto})


@login_required
def cambiar_estado(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Solo admins cambian estado.")
    if request.method == "POST":
        form = CambiarEstadoForm(request.POST)
        if form.is_valid():
            anterior = proyecto.estado
            nuevo = form.cleaned_data["estado"]
            proyecto.estado = nuevo
            if nuevo == "entregado" and form.cleaned_data.get("fecha_real_entrega"):
                proyecto.fecha_real_entrega = form.cleaned_data["fecha_real_entrega"]
            proyecto.save(update_fields=["estado", "fecha_real_entrega", "actualizado_en"])
            emitir(EventoPortavoz(
                tipo="proyecto.status_cambiado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"proyecto_id": proyecto.pk, "anterior": anterior, "nuevo": nuevo},
            ))
            from apps.taller_home.push_handlers import notificar_proyecto_status_cambiado
            notificar_proyecto_status_cambiado(proyecto, anterior, nuevo, request.user)
            messages.success(request, f"Estado: {anterior} → {nuevo}")
            return redirect("proyectos-detalle", pk=proyecto.pk)
    else:
        form = CambiarEstadoForm(initial={"estado": proyecto.estado})
    return render(request, "proyectos/cambiar_estado.html", {"form": form, "proyecto": proyecto})


@login_required
def asignar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Solo admins asignan.")
    if request.method == "POST":
        accion = request.POST.get("accion", "agregar")
        if accion == "quitar":
            ProyectoAsignacion.objects.filter(proyecto=proyecto, pk=request.POST.get("asignacion_id") or 0).delete()
            messages.success(request, "Asignación removida.")
            return redirect("proyectos-asignar", pk=proyecto.pk)
        form = AsignacionForm(request.POST)
        if form.is_valid():
            asig = form.save(commit=False)
            asig.proyecto = proyecto
            try:
                asig.save()
                messages.success(request, f"Asignado {asig.usuario.nombre_completo}.")
            except Exception as exc:
                messages.error(request, f"No se pudo asignar: {exc}")
            return redirect("proyectos-asignar", pk=proyecto.pk)
    else:
        form = AsignacionForm()
    return render(request, "proyectos/asignar.html", {
        "form": form,
        "proyecto": proyecto,
        "asignaciones": proyecto.asignaciones.select_related("usuario"),
    })
