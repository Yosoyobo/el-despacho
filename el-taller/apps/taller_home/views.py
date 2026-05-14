from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from apps.la_cartera.models import Cliente
from apps.los_proyectos.models import Proyecto
from apps.el_pizarron.models import Tarea
from lib.permisos import puede_ver_cartera


@login_required
def home(request):
    rol = getattr(request.user, "rol", None)
    proyectos_visibles = (
        Proyecto.objects.select_related("cliente")
        if rol in ("super_admin", "dueno", "contador")
        else Proyecto.objects.filter(asignaciones__usuario=request.user).select_related("cliente").distinct()
    )
    tareas_pendientes = Tarea.objects.filter(asignada_a=request.user).exclude(estado="completada").select_related("proyecto")
    ctx = {
        "proyectos_recientes": proyectos_visibles.order_by("-creado_en")[:5],
        "tareas_pendientes": tareas_pendientes.order_by("fecha_compromiso")[:8],
        "total_clientes_activos": Cliente.activos.count() if puede_ver_cartera(request.user) else None,
        "puede_ver_cartera": puede_ver_cartera(request.user),
    }
    return render(request, "taller_home/home.html", ctx)


def ping(request):
    return JsonResponse({"ok": True, "app": "el-taller"})
