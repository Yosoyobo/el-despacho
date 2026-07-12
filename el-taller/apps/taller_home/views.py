"""El Dashboard de El Taller (rediseño render-driven S-Dashboard-Render).

Layout fijo dirigido por el render de Learning Center:
1. Topbar "LEARNING CENTER" + encabezado Dashboard.
2. 5 botones de acción pastel.
3. Fila de 3 widgets: Mis tareas · Próximos eventos · Chatbot (El Dictado).
4. 5 KPIs grandes (zona hero).
5. Kanban de 4 columnas activas.
6. Calendario mes actual + siguiente (idéntico al calendario completo).
7. 8 KPIs compactos (los 3 financieros con sparkline de 6 meses).

El render es la base para todos; la zona compacta sigue siendo personalizable
(ocultar/reordenar) vía `PreferenciaKPI`. La zona hero se oculta por tarjeta
con slugs sintéticos `hero-*` desde /perfil/dashboard.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from apps.los_proyectos.models import ESTADOS_PROYECTO, Proyecto
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .kpis import (
    CATEGORIAS,
    ROLES_ADMIN_CONTADOR,
    _kpi_ingresos_mes,
    _kpi_proyectos_activos,
    _kpi_utilidad_mes,
    kpi_por_slug,
    kpis_aplicables_a_rol,
)
from .models import PreferenciaKPI, SugerenciaKPI
from .sugerencias import evaluar_y_persistir, sugerencias_pendientes

ESTADOS_ACTIVOS = ("en_proceso_diseno", "en_proceso_produccion")

_NOMBRES_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

# Slugs del Kanban embebido en el Dashboard (4 columnas activas del render).
KANBAN_SLUGS_DASHBOARD = (
    "por_cotizar", "esperando_respuesta", "en_proceso_diseno", "en_proceso_produccion",
)

# Zona compacta: 8 KPIs del render como default para todos (personalizable).
COMPACT_KPI_SLUGS = (
    "ingresos-mes", "egresos-mes", "utilidad-mes", "cxp-total",
    "tareas-vencidas-equipo", "valor-proyectos", "cxc-total", "cotizaciones-pendientes",
)
# Los 3 primeros llevan sparkline de 6 meses (verde / rojo / azul).
SPARKLINE_FINANCIERO = {
    "ingresos-mes": ("ingresos", "#12b76a"),
    "egresos-mes": ("egresos", "#f04438"),
    "utilidad-mes": ("utilidad", "#465fff"),
}

# Zona hero (5 KPIs grandes). Slugs sintéticos `hero-*` para ocultar por
# tarjeta sin chocar con la zona compacta. (slug, titulo, requiere_finanzas).
HERO_DEFS = (
    ("hero-proyectos-activos", "Proyectos activos", False),
    ("hero-en-produccion", "En producción", False),
    ("hero-tareas-urgentes", "Tareas urgentes", False),
    ("hero-ingresos", "Ingresos del mes", True),
    ("hero-utilidad", "Utilidad bruta del mes", True),
)


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


def _puede_finanzas(rol) -> bool:
    return rol in ROLES_ADMIN_CONTADOR


def _hero_kpis(user, rol) -> list[dict]:
    """Las 5 KPIs grandes del render. Slugs sintéticos `hero-*` para poder
    ocultarlas por tarjeta desde /perfil/dashboard sin chocar con la zona
    compacta. Las financieras sólo para roles con acceso a finanzas."""
    from apps.el_pizarron.models import Tarea

    ocultos = set(
        PreferenciaKPI.objects.filter(usuario=user, visible=False, kpi_slug__startswith="hero-")
        .values_list("kpi_slug", flat=True)
    )
    mes = _NOMBRES_MESES[date.today().month - 1]

    en_produccion = Proyecto.activos.filter(estado="en_proceso_produccion")
    if rol == "disenador":
        en_produccion = en_produccion.filter(asignaciones__usuario=user).distinct()
    tareas_urgentes = Tarea.objects.filter(prioridad="alta").exclude(estado="completada")
    if rol == "disenador":
        tareas_urgentes = tareas_urgentes.filter(asignada_a=user)

    candidatos: list[dict] = [
        {"slug": "hero-proyectos-activos", "titulo": "Proyectos activos",
         **_kpi_proyectos_activos(user)},
        {"slug": "hero-en-produccion", "titulo": "En producción",
         "valor": en_produccion.count(), "nota": "", "link": "/proyectos/?estado=en_proceso_produccion"},
        {"slug": "hero-tareas-urgentes", "titulo": "Tareas urgentes",
         "valor": tareas_urgentes.count(),
         "nota": ("alerta" if tareas_urgentes.exists() else ""), "link": "/tareas/?estado=pendiente"},
    ]
    if _puede_finanzas(rol):
        candidatos.append({"slug": "hero-ingresos", "titulo": f"Ingresos {mes}",
                           **_kpi_ingresos_mes(user)})
        candidatos.append({"slug": "hero-utilidad", "titulo": f"Utilidad bruta {mes}",
                           **_kpi_utilidad_mes(user)})
    return [
        {**c, "alerta": c.get("nota") == "alerta"}
        for c in candidatos if c["slug"] not in ocultos
    ]


def _compact_kpis(user, rol) -> list[dict]:
    """Los 8 KPIs compactos: default del render, filtrados por rol, honrando
    `PreferenciaKPI` (oculto + orden). Los 3 financieros llevan sparkline 6m."""
    ocultos = set(
        PreferenciaKPI.objects.filter(usuario=user, visible=False).values_list("kpi_slug", flat=True)
    )
    ordenes = dict(
        PreferenciaKPI.objects.filter(usuario=user).values_list("kpi_slug", "orden")
    )

    spark = {}
    if _puede_finanzas(rol):
        try:
            from apps.tesoreria.services import series_mensuales_6m
            spark = series_mensuales_6m()
        except Exception:  # noqa: BLE001
            spark = {}

    salida: list[dict] = []
    # Candidatos = los 8 del render (orden 0..7) + KPIs custom del usuario
    # (S2b.5, orden 100+i) para que la personalización siga apareciendo aquí.
    from .kpis import _kpis_custom_para
    candidatos: list[tuple[int, object]] = [
        (i, kpi_por_slug(slug)) for i, slug in enumerate(COMPACT_KPI_SLUGS)
    ]
    candidatos += [(100 + i, kpi) for i, kpi in enumerate(_kpis_custom_para(user))]

    for orden_default, kpi in candidatos:
        if kpi is None or rol not in kpi.roles_visible or kpi.slug in ocultos:
            continue
        try:
            res = kpi.calcular(user)
        except Exception:  # noqa: BLE001 — un KPI roto no tumba el dashboard
            res = {"valor": "?", "nota": "error", "link": ""}
        item = {
            "slug": kpi.slug,
            "titulo": kpi.titulo,
            "valor": res.get("valor", "—"),
            "nota": res.get("nota", ""),
            "alerta": res.get("nota", "") == "alerta",
            "link": res.get("link", ""),
            "orden_default": orden_default,
        }
        if kpi.slug in SPARKLINE_FINANCIERO and spark:
            clave, color = SPARKLINE_FINANCIERO[kpi.slug]
            item["sparkline_serie"] = json.dumps(spark.get(clave, []))
            item["sparkline_color"] = color
        salida.append(item)

    salida.sort(key=lambda it: ordenes[it["slug"]] if ordenes.get(it["slug"]) is not None else 1000 + it["orden_default"])
    return salida


def _mis_tareas(user):
    """Tareas asignadas a mí (o donde soy el runner), sin completadas."""
    from apps.el_pizarron.models import Tarea
    from django.db.models import Q
    qs = (
        Tarea.objects.filter(Q(asignada_a=user) | Q(responsables=user) | Q(runner=user))
        .exclude(estado="completada")
        .filter(archivada=False)  # LC #154: las archivadas no saturan el Dashboard
        .select_related("proyecto__cliente")
        .order_by("fecha_compromiso")
        .distinct()
    )
    total = qs.count()
    return list(qs[:4]), total


def _es_runner(user) -> bool:
    from lib.permisos import puede_ser_runner
    return puede_ser_runner(user)


def _mis_mandados(user):
    """Mandados abiertos donde soy el runner (para el widget del dashboard)."""
    from apps.el_pizarron.mandados import mandados_visibles
    qs = (
        mandados_visibles(user)
        .filter(tarea__runner=user)
        .exclude(estado__in=("entregado", "cancelado"))
        .order_by("tarea__fecha_compromiso")
    )
    return list(qs[:5])


def _proximos_eventos(user):
    """Entregas de proyectos + tareas con fecha, desde hoy. (V6: el estado
    `bloqueada` ya no existe — sin exclusiones especiales.)"""
    from apps.calendario.services import eventos_por_dia
    hoy = date.today()
    fin = hoy + timedelta(days=90)
    evmap = eventos_por_dia(user, hoy, fin)
    items = []
    for f in sorted(evmap.keys()):
        for ev in evmap[f]:
            items.append({**ev, "fecha": f})
    return items[:4], max(0, len(items) - 4)


def _kanban_cols(user):
    """4 columnas activas del Kanban, reusando la lógica de la página Kanban."""
    from apps.los_proyectos.views import _proyectos_visibles
    qs = _proyectos_visibles(user).prefetch_related(
        "productos__servicio", "productos__variacion",
        # LC revisión buzón: buscador ampliado del kanban (mismo en Dashboard).
        "productos__proveedor", "asignaciones__usuario", "cliente__contactos",
    )
    labels = dict(ESTADOS_PROYECTO)
    cols = []
    for slug in KANBAN_SLUGS_DASHBOARD:
        proyectos = list(qs.filter(estado=slug).order_by("fecha_compromiso", "-creado_en"))
        cols.append({"slug": slug, "label": labels.get(slug, slug),
                     "proyectos": proyectos, "total": len(proyectos)})
    return cols


def _calendarios(user):
    """Mes actual + siguiente, grids enriquecidos con eventos (igual que la
    vista de Calendario, reusando sus services)."""
    from apps.calendario.services import eventos_por_dia, grid_mes
    hoy = date.today()
    y2, m2 = (hoy.year, hoy.month + 1) if hoy.month < 12 else (hoy.year + 1, 1)

    def _enriquecer(grid):
        evmap = eventos_por_dia(user, grid["inicio"], grid["fin"])
        for semana in grid["semanas"]:
            for celda in semana:
                celda["eventos"] = evmap.get(celda["fecha"], [])
        return grid

    return {
        "actual": {
            "grid": _enriquecer(grid_mes(hoy.year, hoy.month)),
            "nombre_mes": _NOMBRES_MESES[hoy.month - 1], "year": hoy.year,
        },
        "siguiente": {
            "grid": _enriquecer(grid_mes(y2, m2)),
            "nombre_mes": _NOMBRES_MESES[m2 - 1], "year": y2,
        },
    }


def _propuestas_chalan(user):
    """Propuestas proactivas pendientes de El Chalán para este usuario (Fase 3)."""
    from apps.el_dictado.models import PropuestaChalan
    return list(
        PropuestaChalan.objects.filter(usuario=user, estado="pendiente")
        .select_related("dictado")[:5]
    )


@login_required
def home(request):
    user = request.user
    rol = getattr(user, "rol", None)

    # Capa 2: evalúa reglas heurísticas — crea SugerenciaKPI (se ven en
    # /perfil/dashboard; el banner ya no vive en el home).
    import contextlib
    with contextlib.suppress(Exception):
        evaluar_y_persistir(user)

    mis_tareas, mis_tareas_total = _safe("mis_tareas", lambda: _mis_tareas(user), ([], 0))
    proximos, proximos_mas = _safe("proximos_eventos", lambda: _proximos_eventos(user), ([], 0))
    kanban_cols = _safe("kanban_cols", lambda: _kanban_cols(user), [])
    hero_kpis = _safe("hero_kpis", lambda: _hero_kpis(user, rol), [])
    compact_kpis = _safe("compact_kpis", lambda: _compact_kpis(user, rol), [])
    calendarios = _safe("calendarios", lambda: _calendarios(user),
                        {"actual": None, "siguiente": None})
    # S-Mandados-V2: protagonismo para repartidores — widget de sus mandados.
    es_runner = _safe("es_runner", lambda: _es_runner(user), False)
    mis_mandados = _safe("mis_mandados", lambda: _mis_mandados(user), []) if es_runner else []
    propuestas_chalan = _safe("propuestas_chalan", lambda: _propuestas_chalan(user), [])

    return render(request, "taller_home/home.html", {
        "titulo": "LEARNING CENTER",
        "hoy": date.today(),
        "propuestas_chalan": propuestas_chalan,
        "mis_tareas": mis_tareas,
        "mis_tareas_total": mis_tareas_total,
        "mis_tareas_mas": max(0, mis_tareas_total - len(mis_tareas)),
        "proximos_eventos": proximos,
        "proximos_eventos_mas": proximos_mas,
        "kanban_cols": kanban_cols,
        "hero_kpis": hero_kpis,
        "compact_kpis": compact_kpis,
        "calendarios": calendarios,
        "es_runner": es_runner,
        "mis_mandados": mis_mandados,
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

    # Tarjetas del header (zona hero) — toggle por tarjeta. Default visible.
    hero_ocultos = set(
        PreferenciaKPI.objects.filter(usuario=user, visible=False, kpi_slug__startswith="hero-")
        .values_list("kpi_slug", flat=True)
    )
    hero_cards = [
        {"slug": slug, "titulo": titulo, "visible": slug not in hero_ocultos}
        for slug, titulo, requiere_finanzas in HERO_DEFS
        if (not requiere_finanzas) or _puede_finanzas(rol)
    ]

    return render(request, "taller_home/dashboard_preferencias.html", {
        "grupos": grupos,
        "sugerencias": sugerencias,
        "hero_cards": hero_cards,
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

    # Tarjetas del header (zona hero) — checkboxes `hero_visible`.
    hero_marcados = set(request.POST.getlist("hero_visible"))
    for slug, _titulo, requiere_finanzas in HERO_DEFS:
        if requiere_finanzas and not _puede_finanzas(rol):
            continue
        PreferenciaKPI.objects.update_or_create(
            usuario=user, kpi_slug=slug,
            defaults={"visible": slug in hero_marcados, "origen": "hero"},
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
