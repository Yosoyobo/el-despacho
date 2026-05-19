"""La Sala de Juntas (Pre-S2b.2 — movida desde La Gerencia).

Tres bloques:
1. Slot del Chalán placeholder (mismo de Pre-S2b.1, contrato preservado).
2. KPIs adaptativos por rol — placeholders `--` hasta S2b.4.
3. Dos tablas con datos REALES: proyectos activos por fecha + pendientes
   de cotizar. No son "KPIs nuevos" — son listas existentes filtradas.
"""

from datetime import date

from apps.el_pizarron.models import Tarea
from apps.los_proyectos.models import Proyecto
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

ESTADOS_ACTIVOS = ("en_diseno", "revision_cliente", "en_produccion")


@login_required
def home(request):
    user = request.user
    rol = getattr(user, "rol", None)

    # 1) KPIs adaptativos por rol — placeholders hasta S2b.4.
    if rol in ("super_admin", "dueno"):
        kpis = [
            {"etiqueta": "Pipeline ganado (mes)", "valor": "—", "nota": "S2b.4"},
            {"etiqueta": "Pipeline prospectado", "valor": "—", "nota": "S2b.4"},
            {"etiqueta": "Ingresos del mes", "valor": "—", "nota": "S2b.4"},
            {"etiqueta": "Cuentas por cobrar", "valor": "—", "nota": "S2b.4"},
        ]
    elif rol == "contador":
        kpis = [
            {"etiqueta": "Ingresos del mes", "valor": "—", "nota": "S2b.4"},
            {"etiqueta": "Cuentas por cobrar", "valor": "—", "nota": "S2b.4"},
            {"etiqueta": "Reembolsos pendientes", "valor": "—", "nota": "S2b.4"},
        ]
    else:  # disenador
        mis_proyectos = Proyecto.objects.filter(
            asignaciones__usuario=user, estado__in=ESTADOS_ACTIVOS
        ).distinct().count()
        mis_tareas = Tarea.objects.filter(asignada_a=user).exclude(estado="completada").count()
        kpis = [
            {"etiqueta": "Mis proyectos activos", "valor": str(mis_proyectos), "nota": ""},
            {"etiqueta": "Mis tareas próximas", "valor": str(mis_tareas), "nota": ""},
        ]

    # 2) Tabla "Proyectos activos por fecha" — datos reales.
    proyectos_activos_qs = Proyecto.objects.filter(
        estado__in=ESTADOS_ACTIVOS,
    ).select_related("cliente").order_by("fecha_compromiso", "-creado_en")
    # Diseñador solo ve donde está asignado.
    if rol == "disenador":
        proyectos_activos_qs = proyectos_activos_qs.filter(asignaciones__usuario=user).distinct()
    proyectos_activos = list(proyectos_activos_qs[:10])

    # 3) Tabla "Pendientes de cotizar" — datos reales.
    pendientes_cotizar_qs = Proyecto.objects.filter(
        estado="prospecto",
    ).select_related("cliente").order_by("-creado_en")
    if rol == "disenador":
        pendientes_cotizar_qs = pendientes_cotizar_qs.filter(asignaciones__usuario=user).distinct()
    pendientes_cotizar = list(pendientes_cotizar_qs[:8])

    return render(request, "taller_home/home.html", {
        "kpis": kpis,
        "proyectos_activos": proyectos_activos,
        "pendientes_cotizar": pendientes_cotizar,
        "hoy": date.today(),
    })


def ping(request):
    return JsonResponse({"ok": True, "app": "el-taller"})
