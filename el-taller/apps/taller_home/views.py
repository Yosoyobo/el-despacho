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
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from lib.graficas import area_mensual, donut_desde_conteo

from .kpis import CATEGORIAS, kpis_aplicables_a_rol, kpis_visibles_para
from .models import PreferenciaKPI, SugerenciaKPI
from .sugerencias import evaluar_y_persistir, sugerencias_pendientes

ESTADOS_ACTIVOS = ("en_proceso_diseno", "en_proceso_produccion")


def _charts_sala_de_juntas(rol: str) -> dict:
    """Series JSON para los charts de la Sala de Juntas.

    - Donut: proyectos por estado.
    - Donut: tareas por estado.
    - Area mensual: ingresos vs egresos últimos 6 meses (si Tesorería tiene datos).
    """
    from apps.el_pizarron.models import Tarea

    proyectos_por_estado = dict(
        Proyecto.objects.values_list("estado").annotate(c=Count("id")).values_list("estado", "c")
    )
    proyectos_etiquetas = dict(
        (slug, label) for slug, label in
        Proyecto._meta.get_field("estado").choices
    )

    tareas_qs = Tarea.objects.exclude(estado="completada")
    tareas_por_estado = dict(
        tareas_qs.values_list("estado").annotate(c=Count("id")).values_list("estado", "c")
    )
    tareas_etiquetas = dict(Tarea._meta.get_field("estado").choices)

    # Ingresos/egresos últimos 6 meses
    hoy = timezone.localdate()
    meses_labels = []
    ing_data = []
    egr_data = []
    try:
        from apps.tesoreria.models import Egreso, Ingreso

        # Genera lista de inicios de mes (6 meses atrás → ahora).
        anchors = []
        y, m = hoy.year, hoy.month
        for _ in range(6):
            anchors.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        anchors.reverse()
        for y, m in anchors:
            meses_labels.append(date(y, m, 1).strftime("%b"))
            ing = Ingreso.vigentes.filter(fecha__year=y, fecha__month=m).aggregate(t=Sum("monto"))["t"] or 0
            egr = Egreso.vigentes.filter(fecha__year=y, fecha__month=m).aggregate(t=Sum("monto"))["t"] or 0
            ing_data.append(ing)
            egr_data.append(egr)
    except Exception:  # noqa: BLE001
        meses_labels = []
        ing_data = []
        egr_data = []

    return {
        "donut_proyectos_json": donut_desde_conteo(proyectos_por_estado, etiquetas=proyectos_etiquetas),
        "donut_tareas_json": donut_desde_conteo(tareas_por_estado, etiquetas=tareas_etiquetas),
        "area_dinero_json": area_mensual(
            meses_labels,
            [
                {"name": "Ingresos", "data": ing_data, "color": "#12b76a"},
                {"name": "Egresos", "data": egr_data, "color": "#f04438"},
            ],
        ) if meses_labels else "",
    }


def _safe(label: str, fn, default):
    """S-LC-Feedback-V4 hotfix: wrapper defensivo. Si una sección del dashboard
    revienta por datos inconsistentes, NO debe tumbar la página entera.
    Log a stderr para que el operador la cace en `docker compose logs`.
    """
    import logging
    log = logging.getLogger("taller_home.dashboard")
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — el dashboard no se tumba por una sección rota
        log.exception("Dashboard: sección %r falló: %s", label, e)
        return default


@login_required
def home(request):
    user = request.user
    rol = getattr(user, "rol", None)

    # Capa 2: evalúa reglas heurísticas — crea SugerenciaKPI nuevas si aplican.
    import contextlib
    with contextlib.suppress(Exception):
        evaluar_y_persistir(user)

    def _build_sugerencias():
        from .kpis import kpi_por_slug
        sugerencias = sugerencias_pendientes(user)
        return [
            {
                "id": s.pk,
                "kpi_slug": s.kpi_slug,
                "titulo": (kpi_por_slug(s.kpi_slug).titulo if kpi_por_slug(s.kpi_slug) else s.kpi_slug),
                "motivo": s.motivo,
            }
            for s in sugerencias
        ]

    sugerencias_view = _safe("sugerencias", _build_sugerencias, [])

    def _build_kpis():
        out = []
        for kpi, resultado in kpis_visibles_para(user):
            out.append({
                "slug": kpi.slug,
                "titulo": kpi.titulo,
                "categoria": kpi.categoria,
                "valor": resultado.get("valor", "—"),
                "nota": resultado.get("nota", ""),
                "link": resultado.get("link", ""),
                "estado_kpi": kpi.estado_kpi,
            })
        return out

    kpis_render = _safe("kpis", _build_kpis, [])

    def _build_proyectos_activos():
        qs = (
            Proyecto.objects.filter(estado__in=ESTADOS_ACTIVOS)
            .select_related("cliente")
            .order_by("fecha_compromiso", "-creado_en")
        )
        if rol == "disenador":
            qs = qs.filter(asignaciones__usuario=user).distinct()
        return list(qs[:10])

    proyectos_activos = _safe("proyectos_activos", _build_proyectos_activos, [])

    def _build_pendientes_cotizar():
        qs = (
            Proyecto.objects.filter(estado="por_cotizar")
            .select_related("cliente")
            .order_by("-creado_en")
        )
        if rol == "disenador":
            qs = qs.filter(asignaciones__usuario=user).distinct()
        return list(qs[:8])

    pendientes_cotizar = _safe("pendientes_cotizar", _build_pendientes_cotizar, [])

    charts = _safe("charts", lambda: _charts_sala_de_juntas(rol or ""), {})

    def _build_mini_cal():
        from apps.calendario.services import datos_mini_cal
        _hoy = date.today()
        _meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        _y2, _m2 = (_hoy.year, _hoy.month + 1) if _hoy.month < 12 else (_hoy.year + 1, 1)
        return {
            "actual": {
                "nombre_mes": f"{_meses[_hoy.month - 1]} {_hoy.year}",
                "datos": datos_mini_cal(user, _hoy.year, _hoy.month),
            },
            "siguiente": {
                "nombre_mes": f"{_meses[_m2 - 1]} {_y2}",
                "datos": datos_mini_cal(user, _y2, _m2),
            },
        }

    mini_cal = _safe(
        "mini_cal",
        _build_mini_cal,
        {"actual": {"nombre_mes": "", "datos": []}, "siguiente": {"nombre_mes": "", "datos": []}},
    )

    # S-Demo-Pre-Showcase: gauges del droplet + tarjetas Chalanes IA.
    # Sólo super_admin/dueno. Best-effort: si los volúmenes /proc no están
    # montados (entorno dev/CI sin docker-compose.site.yml), los partials
    # degradan a "n/d" sin tumbar el home.
    infra_gauges = None
    chalanes_resumen = None
    chalanes_tarjetas = None
    if rol in ("super_admin", "dueno"):
        try:
            from lib.site.gauges import snapshot_gauges_minimo
            infra_gauges = snapshot_gauges_minimo()
        except Exception:  # noqa: BLE001
            infra_gauges = None
        try:
            from lib.analistas.stats import resumen_global, tarjetas_chalanes
            chalanes_resumen = resumen_global(dias=30)
            chalanes_tarjetas = tarjetas_chalanes(dias=30)
        except Exception:  # noqa: BLE001
            chalanes_resumen = None
            chalanes_tarjetas = None

    return render(request, "taller_home/home.html", {
        "kpis": kpis_render,
        "sugerencias": sugerencias_view,
        "proyectos_activos": proyectos_activos,
        "pendientes_cotizar": pendientes_cotizar,
        "hoy": date.today(),
        "charts": charts,
        "mini_cal": mini_cal,
        "infra_gauges": infra_gauges,
        "chalanes_resumen": chalanes_resumen,
        "chalanes_tarjetas": chalanes_tarjetas,
    })


@login_required
def dashboard_preferencias(request):
    """Página de edición de KPIs visibles + sugerencias del Chalán."""
    user = request.user
    rol = getattr(user, "rol", None) or "disenador"
    aplicables = kpis_aplicables_a_rol(rol, user=user)

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
    aplicables_slugs = {k.slug for k in kpis_aplicables_a_rol(rol, user=user)}
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
def dashboard_reordenar(request):
    """POST /perfil/dashboard/reordenar — guarda orden de KPIs vía drag&drop.

    S-LC-Feedback-V3. Body: `slugs[]` lista ordenada de slugs visibles.
    Actualiza `PreferenciaKPI.orden` por usuario (0..N).
    """
    user = request.user
    slugs = request.POST.getlist("slugs")
    if not slugs:
        return JsonResponse({"ok": False, "error": "Vacío."}, status=400)
    for i, slug in enumerate(slugs):
        PreferenciaKPI.objects.update_or_create(
            usuario=user, kpi_slug=slug,
            defaults={"orden": i, "visible": True},
        )
    return JsonResponse({"ok": True, "n": len(slugs)})


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
