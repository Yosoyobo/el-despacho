"""La Sala de Juntas (S2b.4 — KPIs reales + granularidad).

Estructura:
1. Slot del Chalán placeholder (sigue en placeholder hasta S2b.2).
2. Banner de sugerencias del Chalán (Capa 2 — reglas heurísticas).
3. KPIs reales iterando `kpis_visibles_para(user)` (respeta preferencias).
4. Dos tablas con datos reales: proyectos activos + pendientes de cotizar.
"""

from __future__ import annotations

from datetime import date

from apps.los_proyectos.models import Proyecto
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .kpis import CATEGORIAS, kpis_aplicables_a_rol, kpis_visibles_para
from .models import PreferenciaKPI, SugerenciaKPI
from .sugerencias import evaluar_y_persistir, sugerencias_pendientes

ESTADOS_ACTIVOS = ("en_diseno", "revision_cliente", "en_produccion")


@login_required
def home(request):
    user = request.user
    rol = getattr(user, "rol", None)

    # Capa 2: evalúa reglas heurísticas — crea SugerenciaKPI nuevas si aplican.
    import contextlib
    with contextlib.suppress(Exception):
        evaluar_y_persistir(user)

    sugerencias = sugerencias_pendientes(user)
    # Inyectar el título del KPI sugerido para no resolverlo en el template.
    from .kpis import kpi_por_slug
    sugerencias_view = [
        {
            "id": s.pk,
            "kpi_slug": s.kpi_slug,
            "titulo": (kpi_por_slug(s.kpi_slug).titulo if kpi_por_slug(s.kpi_slug) else s.kpi_slug),
            "motivo": s.motivo,
        }
        for s in sugerencias
    ]

    # KPIs visibles para el usuario (catálogo + preferencias).
    kpis_render = []
    for kpi, resultado in kpis_visibles_para(user):
        kpis_render.append({
            "slug": kpi.slug,
            "titulo": kpi.titulo,
            "categoria": kpi.categoria,
            "valor": resultado.get("valor", "—"),
            "nota": resultado.get("nota", ""),
            "link": resultado.get("link", ""),
            "estado_kpi": kpi.estado_kpi,
        })

    # Tabla "Proyectos activos por fecha" — datos reales.
    proyectos_activos_qs = Proyecto.objects.filter(
        estado__in=ESTADOS_ACTIVOS,
    ).select_related("cliente").order_by("fecha_compromiso", "-creado_en")
    if rol == "disenador":
        proyectos_activos_qs = proyectos_activos_qs.filter(asignaciones__usuario=user).distinct()
    proyectos_activos = list(proyectos_activos_qs[:10])

    # Tabla "Pendientes de cotizar" — datos reales.
    pendientes_cotizar_qs = Proyecto.objects.filter(
        estado="prospecto",
    ).select_related("cliente").order_by("-creado_en")
    if rol == "disenador":
        pendientes_cotizar_qs = pendientes_cotizar_qs.filter(asignaciones__usuario=user).distinct()
    pendientes_cotizar = list(pendientes_cotizar_qs[:8])

    return render(request, "taller_home/home.html", {
        "kpis": kpis_render,
        "sugerencias": sugerencias_view,
        "proyectos_activos": proyectos_activos,
        "pendientes_cotizar": pendientes_cotizar,
        "hoy": date.today(),
    })


@login_required
def dashboard_preferencias(request):
    """Página de edición de KPIs visibles + sugerencias del Chalán."""
    user = request.user
    rol = getattr(user, "rol", None) or "disenador"
    aplicables = kpis_aplicables_a_rol(rol)

    ocultos = set(
        PreferenciaKPI.objects.filter(usuario=user, visible=False).values_list("kpi_slug", flat=True)
    )

    # Agrupar por categoría preservando el orden del catálogo CATEGORIAS.
    por_categoria: dict[str, list[dict]] = {cat: [] for cat, _ in CATEGORIAS}
    for kpi in aplicables:
        if kpi.categoria not in por_categoria:
            por_categoria[kpi.categoria] = []
        por_categoria[kpi.categoria].append({
            "slug": kpi.slug,
            "titulo": kpi.titulo,
            "descripcion": kpi.descripcion,
            "visible": kpi.slug not in ocultos,
            "estado_kpi": kpi.estado_kpi,
        })

    grupos = [
        {"categoria": cat, "etiqueta": etiqueta, "kpis": por_categoria.get(cat, [])}
        for cat, etiqueta in CATEGORIAS
        if por_categoria.get(cat)
    ]
    sugerencias = sugerencias_pendientes(user)

    return render(request, "taller_home/dashboard_preferencias.html", {
        "grupos": grupos,
        "sugerencias": sugerencias,
    })


@login_required
@require_http_methods(["POST"])
def dashboard_guardar(request):
    """Guarda visibles[] de la página de preferencias. Slugs no marcados → ocultos."""
    user = request.user
    rol = getattr(user, "rol", None) or "disenador"
    aplicables_slugs = {k.slug for k in kpis_aplicables_a_rol(rol)}
    marcados = set(request.POST.getlist("visible"))

    for slug in aplicables_slugs:
        visible = slug in marcados
        PreferenciaKPI.objects.update_or_create(
            usuario=user, kpi_slug=slug, defaults={"visible": visible, "origen": "manual"},
        )
    from django.contrib import messages
    messages.success(request, "Preferencias del dashboard guardadas.")
    from django.shortcuts import redirect
    return redirect("perfil-dashboard")


@login_required
@require_http_methods(["POST"])
def sugerencia_aceptar(request, sugerencia_id: int):
    """Acepta la sugerencia: activa la PreferenciaKPI + marca aceptada."""
    from django.shortcuts import get_object_or_404, redirect

    sug = get_object_or_404(SugerenciaKPI, pk=sugerencia_id, usuario=request.user, estado="pendiente")
    PreferenciaKPI.objects.update_or_create(
        usuario=request.user, kpi_slug=sug.kpi_slug,
        defaults={"visible": True, "origen": "sugerido_chalan"},
    )
    sug.estado = "aceptada"
    sug.resuelta_en = timezone.now()
    sug.save(update_fields=["estado", "resuelta_en"])
    from django.contrib import messages
    messages.success(request, f"KPI activado: {sug.kpi_slug}")
    return redirect(request.META.get("HTTP_REFERER") or "perfil-dashboard")


@login_required
@require_http_methods(["POST"])
def sugerencia_descartar(request, sugerencia_id: int):
    """Descarta la sugerencia — no se volverá a sugerir el mismo slug."""
    from django.shortcuts import get_object_or_404, redirect

    sug = get_object_or_404(SugerenciaKPI, pk=sugerencia_id, usuario=request.user, estado="pendiente")
    sug.estado = "descartada"
    sug.resuelta_en = timezone.now()
    sug.save(update_fields=["estado", "resuelta_en"])
    return redirect(request.META.get("HTTP_REFERER") or "perfil-dashboard")


def ping(request):
    return JsonResponse({"ok": True, "app": "el-taller"})
