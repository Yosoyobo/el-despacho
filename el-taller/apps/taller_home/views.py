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

import contextlib
import json
from datetime import date, timedelta
from urllib.parse import quote

from apps.los_proyectos.models import ESTADOS_PROYECTO, Proyecto
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from lib.busqueda import q_texto

from .kpis import (
    CATEGORIAS,
    _kpi_ingresos_mes,
    _kpi_proyectos_activos,
    _kpi_utilidad_mes,
    kpi_por_slug,
    kpis_aplicables,
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

# Los 8 KPIs que el Inicio pintaba fijos hasta S-KPIs-V2. Hoy son el tablero
# por omisión (`TableroKPI(rol=None)`, sembrado en taller_home/0007); se
# conservan aquí como referencia para las pruebas y el Chalán.
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


# La tarjeta grande que es el mismo número que un KPI del catálogo (su meta).
HERO_KPI = {
    "hero-proyectos-activos": "proyectos-activos",
    "hero-ingresos": "ingresos-mes",
    "hero-utilidad": "utilidad-mes",
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


def _puede_finanzas(user) -> bool:
    """Las tarjetas de dinero del Inicio: `tesoreria.ver`, lo mismo que abre La
    Tesorería (antes, el rol PRIMARIO super_admin/dueño/contador)."""
    from lib.permisos import puede_ver_finanzas
    return puede_ver_finanzas(user)


def _solo_lo_suyo(user) -> bool:
    """¿Los conteos del hero se acotan a lo de `user`? Quien ve proyectos
    pero no todos (`proyectos.ver` sin `ver_todos`); antes, el rol PRIMARIO
    diseñador."""
    from lib.permisos import solo_proyectos_asignados
    return solo_proyectos_asignados(user)


def _hero_kpis(user) -> list[dict]:
    """Las 5 KPIs grandes del render. Slugs sintéticos `hero-*` para poder
    ocultarlas por tarjeta desde /perfil/dashboard sin chocar con la zona
    compacta. Las financieras sólo para quien ve el dinero (`tesoreria.ver`)."""
    from apps.el_pizarron.models import Tarea

    ocultos = set(
        PreferenciaKPI.objects.filter(usuario=user, visible=False, kpi_slug__startswith="hero-")
        .values_list("kpi_slug", flat=True)
    )
    mes = _NOMBRES_MESES[date.today().month - 1]

    solo_lo_suyo = _solo_lo_suyo(user)
    en_produccion = Proyecto.activos.filter(estado="en_proceso_produccion")
    if solo_lo_suyo:
        en_produccion = en_produccion.filter(asignaciones__usuario=user).distinct()
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    tareas_urgentes = (
        Tarea.objects.filter(prioridad="alta", archivada=False)
        # Todos los estados terminales (configurables en Gerencia), no sólo
        # el literal «completada».
        .exclude(estado__in=slugs_terminales_tarea())
    )
    if solo_lo_suyo:
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
    if _puede_finanzas(user):
        candidatos.append({"slug": "hero-ingresos", "titulo": f"Ingresos {mes}",
                           **_kpi_ingresos_mes(user)})
        candidatos.append({"slug": "hero-utilidad", "titulo": f"Utilidad bruta {mes}",
                           **_kpi_utilidad_mes(user)})
    # La zona grande también lleva la meta de su KPI (S-KPIs-V2).
    from .kpi_valor import numero_del_resultado
    from .metas import meta_para_tarjeta
    from .tablero import configs, efectivo

    cfgs = configs()
    salida = []
    for c in candidatos:
        if c["slug"] in ocultos:
            continue
        item = {**c, "alerta": c.get("nota") == "alerta"}
        kpi = kpi_por_slug(HERO_KPI.get(c["slug"], ""))
        if kpi is not None:
            with contextlib.suppress(Exception):
                item["meta"] = meta_para_tarjeta(
                    user, efectivo(kpi, cfgs), numero_del_resultado(c),
                )
        salida.append(item)
    return salida


def _compact_kpis(user) -> list[dict]:
    """«Tu tablero»: el tablero de los roles de `user` armado en La Gerencia,
    con lo que la persona ocultó o agregó (S-KPIs-V2, `tablero.py`). Cada
    tarjeta trae su formato, su semáforo y su meta; los 3 financieros, su
    sparkline de 6 meses, y el resto, la de su foto diaria si ya tiene."""
    from . import series
    from .models import MetaKPI
    from .tablero import configs, kpis_del_tablero, tarjeta

    cfgs = configs()
    metas = list(MetaKPI.objects.filter(activa=True))

    spark = {}
    if _puede_finanzas(user):
        try:
            from apps.tesoreria.services import series_mensuales_6m
            spark = series_mensuales_6m()
        except Exception:  # noqa: BLE001
            spark = {}

    salida: list[dict] = []
    for kpi in kpis_del_tablero(user):
        try:
            res = kpi.calcular(user)
        except Exception:  # noqa: BLE001 — un KPI roto no tumba el dashboard
            res = {"valor": "?", "nota": "error", "link": ""}
        historia = None
        if kpi.slug not in SPARKLINE_FINANCIERO and not kpi.personal and not (
            kpi.acotado and _solo_lo_suyo(user)
        ):
            with contextlib.suppress(Exception):
                historia = [p["valor"] for p in series.serie(kpi.slug, dias=30)]
        item = tarjeta(user, kpi, res, cfgs=cfgs, metas=metas, sparkline=historia)
        if kpi.slug in SPARKLINE_FINANCIERO and spark:
            clave, color = SPARKLINE_FINANCIERO[kpi.slug]
            item["sparkline_serie"] = json.dumps(spark.get(clave, []))
            item["sparkline_color"] = color
        salida.append(item)
    return salida


def _mis_tareas(user):
    """Tareas pendientes del despacho — las de TODOS, no sólo las mías.

    LC 2026-07-29 (Oscar): el recuadro pasó de «Mis tareas» a «Tareas
    pendientes» mostrando las de todo el equipo. La visibilidad la sigue
    resolviendo `_tareas_visibles` de la página de Tareas (misma fuente), así que
    quien sólo ve lo suyo —un runner, un diseñador— sigue viendo sólo lo suyo.

    El nombre de la función se conserva: es lo que consume el Dashboard y
    renombrarlo no aporta.
    """
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    from apps.el_pizarron.views import _tareas_visibles
    qs = (
        _tareas_visibles(user)
        # Los estados terminales son CONFIGURABLES en Gerencia, así que se
        # excluyen todos — no sólo el literal "completada". Con el recuadro
        # mostrando lo de todo el equipo, una tarea cerrada en otro estado
        # terminal se colaba como «pendiente».
        .exclude(estado__in=slugs_terminales_tarea())
        .filter(archivada=False)  # LC #154: las archivadas no saturan el Dashboard
        .select_related("proyecto__cliente", "asignada_a")
        .order_by("fecha_compromiso")
        .distinct()
    )
    total = qs.count()
    return list(qs[:4]), total


def _es_runner(user) -> bool:
    from lib.permisos import puede_ser_runner
    return puede_ser_runner(user)


def _mis_mandados(user):
    """Mandados abiertos donde soy el runner (para el widget del dashboard).

    Buzón #155/#165: además del estado del reparto se mira la TAREA —que siga
    siendo entrega/recoger, sin cerrar y sin archivar—. Si el mandado se quedó
    atrás (la tarea cambió de tipo o se cerró por otro lado), no se cuela.
    """
    from apps.el_pizarron.mandados import TIPOS_RUNNER, mandados_visibles
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    qs = (
        mandados_visibles(user)
        .filter(tarea__runner=user, tarea__tipo__in=TIPOS_RUNNER, tarea__archivada=False)
        .exclude(estado__in=("entregado", "cancelado"))
        .exclude(tarea__estado__in=slugs_terminales_tarea())
        .order_by("tarea__fecha_compromiso")
    )
    return list(qs[:5])


def _chat_acepta_imagenes(user) -> bool:
    """True si el Chalán de la estación del chat sabe leer imágenes."""
    from apps.el_dictado.services_chat import chat_acepta_imagenes
    return chat_acepta_imagenes(user)


def _proximos_eventos(user):
    """Entregas de proyectos + tareas con fecha, desde hoy. (V6: el estado
    `bloqueada` ya no existe — sin exclusiones especiales.)

    LC 2026-08-04 R3 (Oscar): la fecha de entrega de un proyecto sólo cuenta como
    evento **de En proceso de diseño en adelante**. Un proyecto por cotizar o
    esperando respuesta todavía no tiene compromiso real y ensuciaba el widget.
    La regla vive SÓLO aquí: la página del Calendario sigue mostrando todo.
    """
    from apps.calendario.services import eventos_por_dia
    from apps.los_proyectos.models import slugs_con_compromiso_visible
    hoy = date.today()
    fin = hoy + timedelta(days=90)
    evmap = eventos_por_dia(user, hoy, fin)
    con_compromiso = slugs_con_compromiso_visible()
    items = []
    for f in sorted(evmap.keys()):
        for ev in evmap[f]:
            if ev.get("tipo") == "entrega" and ev.get("estado") not in con_compromiso:
                continue
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
        # LC 2026-08-04 R3: mismo orden manual que la página Kanban.
        proyectos = list(qs.filter(estado=slug).order_by("orden_kanban", "fecha_compromiso", "-creado_en"))
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


# Cuántos resultados «fuera del tablero» se listan antes de mandar a la lista.
MAX_RESULTADOS_FUERA = 40

# Las 4 columnas del «tablero inactivo» — las mismas, y en el mismo orden, que
# la fila de abajo de la página Kanban (LC 2026-08-13, Oscar: «que los muestre
# en los mismos recuadros de esas 4 categorías, divididas en 4 para caber en 1
# fila»).
KANBAN_SLUGS_FUERA = ("en_pausa", "entregado", "cerrado", "cancelado")


@login_required
def buscar_proyectos(request):
    """Busca lo que el tablero del Dashboard NO puede mostrar (LC 2026-08-12).

    El Dashboard sólo pinta las cuatro columnas activas, así que un proyecto
    entregado, cerrado o cancelado no está en la página y el filtro instantáneo
    del navegador jamás lo encontraría. Aquí se busca del lado del servidor y se
    devuelven SÓLO los que quedan fuera del tablero — los que sí están los sigue
    filtrando el buscador al instante, sin esperar a la red.

    LC 2026-08-13 (Oscar): los resultados ya no salen como una lista suelta sino
    repartidos en las MISMAS cuatro columnas del tablero de abajo (en pausa,
    entregado, cerrado, cancelado), con su contador — «0, 0, 1 y 0».

    Respeta la visibilidad de siempre (`_proyectos_visibles`).
    """
    from apps.los_proyectos.views import _proyectos_visibles

    q = (request.GET.get("q") or "").strip()
    ctx = {"q": q, "cols": [], "total": 0, "hay_mas": False}
    if len(q) < 2:
        return render(request, "taller_home/_kanban_resultados_fuera.html", ctx)

    qs = (
        _proyectos_visibles(request.user)
        .exclude(estado__in=KANBAN_SLUGS_DASHBOARD)
        .filter(q_texto(
            q, "nombre", "codigo", "cliente__razon_social",
            "productos__nombre_proyecto", "productos__servicio__nombre",
            "productos__proveedor__razon_social",
        ))
        .select_related("cliente")
        .prefetch_related("productos__servicio", "productos__variacion")
        .distinct()
        .order_by("orden_kanban", "-actualizado_en")
    )
    encontrados = list(qs[: MAX_RESULTADOS_FUERA + 1])
    ctx["hay_mas"] = len(encontrados) > MAX_RESULTADOS_FUERA
    encontrados = encontrados[:MAX_RESULTADOS_FUERA]
    ctx["total"] = len(encontrados)

    labels = dict(ESTADOS_PROYECTO)
    por_estado: dict[str, list] = {slug: [] for slug in KANBAN_SLUGS_FUERA}
    otros: list = []
    for p in encontrados:
        por_estado.get(p.estado, otros).append(p)
    # Un estado custom (fuera de los 4 canónicos) no se pierde: se agrega su
    # propia columna al final.
    for p in otros:
        por_estado.setdefault(p.estado, []).append(p)
    ctx["cols"] = [
        {"slug": slug, "label": labels.get(slug, slug),
         "proyectos": lista, "total": len(lista)}
        for slug, lista in por_estado.items()
    ]
    ctx["secciones"] = _buscar_otras_fichas(request.user, q)
    return render(request, "taller_home/_kanban_resultados_fuera.html", ctx)


# Tope por sección del buscador del Dashboard. Es un atajo, no una lista: quien
# quiera verlas todas tiene el enlace a su pantalla con el término puesto.
MAX_POR_SECCION = 8


def _buscar_otras_fichas(usuario, q: str) -> list[dict]:
    """Clientes, productos y proveedores que empatan con `q` (LC 2026-08-28).

    Oscar: «en búsqueda del dashboard mostrar también clientes, etc. en
    resultados fuera del tablero».

    Los criterios NO se reinventan: son los mismos que usan la lista de Clientes
    (`_buscar_clientes`) y las de Productos y Proveedores del Catálogo, para que
    buscar desde el Dashboard encuentre exactamente lo mismo que buscar allá.

    Sin el permiso del módulo, la sección **no aparece** — ni siquiera como un
    «no puedes». Cada bloque nunca lanza: una sección que falle se salta y las
    demás se pintan igual.
    """
    from django.urls import reverse

    from lib.permisos import puede_ver_cartera, puede_ver_catalogo
    secciones: list[dict] = []
    # El gate del Catálogo es `catalogo.ver_nombres`, el mismo que usa su propia
    # lista. `puede_ver_catalogo` preguntaba por una acción `catalogo.ver` que no
    # existe (devolvía False para todos); desde S-Deuda-Sep28 ya pregunta por la
    # correcta y este es su primer uso.
    ve_catalogo = puede_ver_catalogo(usuario)

    def _agregar(titulo, icono, qs, fila, url_todos):
        filas = list(qs[: MAX_POR_SECCION + 1])
        if not filas:
            return
        hay_mas = len(filas) > MAX_POR_SECCION
        secciones.append({
            "titulo": titulo, "icono": icono,
            "items": [fila(o) for o in filas[:MAX_POR_SECCION]],
            "total": len(filas[:MAX_POR_SECCION]),
            "hay_mas": hay_mas,
            "url_todos": f"{url_todos}?q={quote(q)}",
        })

    if puede_ver_cartera(usuario):
        with contextlib.suppress(Exception):
            from apps.la_cartera.models import Cliente
            from apps.la_cartera.views import _buscar_clientes
            _agregar(
                "Clientes", "👤",
                _buscar_clientes(Cliente.objects.all(), q).order_by("razon_social"),
                lambda c: {
                    "titulo": c.razon_social,
                    "sub": c.razon_social_fiscal or c.nombre_contacto or c.rfc or "",
                    "url": reverse("cartera-detalle", args=[c.pk]),
                },
                reverse("cartera-lista"),
            )

    if ve_catalogo:
        with contextlib.suppress(Exception):
            from apps.el_catalogo.models import Servicio
            _agregar(
                "Productos", "📦",
                (Servicio.objects.filter(activo=True)
                 .filter(q_texto(q, "nombre", "proveedores__razon_social",
                                 "en_proyectos__nombre_proyecto"))
                 .select_related("categoria").distinct().order_by("nombre")),
                lambda s: {
                    "titulo": s.nombre,
                    "sub": s.categoria.nombre if s.categoria_id else "",
                    "url": reverse("catalogo-editar", args=[s.pk]),
                },
                reverse("catalogo-lista"),
            )
        with contextlib.suppress(Exception):
            from apps.el_catalogo.models import Proveedor
            _agregar(
                "Proveedores", "🏭",
                (Proveedor.objects.filter(activo=True)
                 .filter(q_texto(q, "razon_social", "nombre_contacto", "email_contacto",
                                 "telefono", "subcategorias__nombre",
                                 "subcategorias__categoria__nombre", "servicios__nombre"))
                 .distinct().order_by("razon_social")),
                lambda pr: {
                    "titulo": pr.razon_social,
                    "sub": pr.nombre_contacto or "",
                    "url": reverse("catalogo-proveedor-detalle", args=[pr.pk]),
                },
                reverse("catalogo-proveedores"),
            )

    return secciones


def _infra_gauges(user):
    """Los cuatro relojes del NUC para el pie del Dashboard.

    Oscar los pidió ahí (2026-08-24) para ver de un vistazo cómo va la máquina
    sin salir a La Gerencia. El partial ya existía desde S-Demo-Pre-Showcase
    pero había quedado huérfano: nadie lo incluía.

    Se gatea con `site.ver` —el mismo permiso que abre El Site— y no por rol
    literal (§4 #20). Devuelve None si no hay permiso o si no se puede medir,
    y entonces la sección no se pinta.
    """
    from lib.permisos import puede

    if not puede(user, "site", "ver"):
        return None
    from lib.site.fierro import contexto

    datos = contexto()
    # Sin /proc montado no hay nada que enseñar; mejor no pintar la sección que
    # pintar cuatro relojes en «n/d».
    if not datos or not datos.get("disponible"):
        return None
    return datos


@login_required
def home(request):
    user = request.user

    # Capa 2: evalúa reglas heurísticas — crea SugerenciaKPI (se ven en
    # /perfil/dashboard; el banner ya no vive en el home).
    import contextlib
    with contextlib.suppress(Exception):
        evaluar_y_persistir(user)

    mis_tareas, mis_tareas_total = _safe("mis_tareas", lambda: _mis_tareas(user), ([], 0))
    proximos, proximos_mas = _safe("proximos_eventos", lambda: _proximos_eventos(user), ([], 0))
    kanban_cols = _safe("kanban_cols", lambda: _kanban_cols(user), [])
    hero_kpis = _safe("hero_kpis", lambda: _hero_kpis(user), [])
    compact_kpis = _safe("compact_kpis", lambda: _compact_kpis(user), [])
    calendarios = _safe("calendarios", lambda: _calendarios(user),
                        {"actual": None, "siguiente": None})
    # S-Mandados-V2: protagonismo para repartidores — widget de sus mandados.
    es_runner = _safe("es_runner", lambda: _es_runner(user), False)
    mis_mandados = _safe("mis_mandados", lambda: _mis_mandados(user), []) if es_runner else []
    propuestas_chalan = _safe("propuestas_chalan", lambda: _propuestas_chalan(user), [])
    # LC 2026-07-28 (Oscar): el mini Chalán del Dashboard acepta foto adjunta,
    # pero sólo si el Chalán configurado para el chat tiene visión.
    chat_vision_ok = _safe("chat_vision_ok", lambda: _chat_acepta_imagenes(user), False)
    # Los cuatro relojes del NUC, al pie del tablero.
    infra_gauges = _safe("infra_gauges", lambda: _infra_gauges(user), None)

    return render(request, "taller_home/home.html", {
        "infra_gauges": infra_gauges,
        "chat_vision_ok": chat_vision_ok,
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
    from .tablero import base_de, kpis_del_tablero

    user = request.user
    aplicables = kpis_aplicables(user)
    en_tablero = {k.slug for k in kpis_del_tablero(user)}
    de_tu_rol = set(base_de(user))

    # Agrupar por categoría preservando el orden del catálogo CATEGORIAS.
    por_categoria: dict[str, list[dict]] = {cat: [] for cat, _ in CATEGORIAS}
    for kpi in aplicables:
        if kpi.categoria not in por_categoria:
            por_categoria[kpi.categoria] = []
        por_categoria[kpi.categoria].append({
            "slug": kpi.slug,
            "titulo": kpi.titulo,
            "descripcion": kpi.descripcion,
            "visible": kpi.slug in en_tablero,
            "de_tu_rol": kpi.slug in de_tu_rol,
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
        if (not requiere_finanzas) or _puede_finanzas(user)
    ]

    return render(request, "taller_home/dashboard_preferencias.html", {
        "grupos": grupos,
        "sugerencias": sugerencias,
        "hero_cards": hero_cards,
    })


@login_required
@require_http_methods(["POST"])
def dashboard_guardar(request):
    """Guarda la página de preferencias: SÓLO lo que difiere del tablero del rol.

    Marcado y en la base de su rol → sin fila (sigue al rol); desmarcado y en
    la base → `visible=False`; marcado y fuera de la base → `visible=True`. Así
    un cambio del tablero del rol en La Gerencia le llega a quien no lo tocó.
    (Hasta S-KPIs-V2 escribía una fila por CADA KPI del catálogo.)"""
    from .tablero import base_de

    user = request.user
    aplicables_slugs = {k.slug for k in kpis_aplicables(user)}
    marcados = set(request.POST.getlist("visible"))
    base = set(base_de(user))

    for slug in aplicables_slugs:
        visible = slug in marcados
        # Los KPIs del Chalán entran solos, como si fueran de la base.
        en_base = slug in base or slug.startswith("custom-")
        pref = PreferenciaKPI.objects.filter(usuario=user, kpi_slug=slug).first()
        if visible == en_base:
            if pref is not None and pref.orden is None:
                pref.delete()
            elif pref is not None and pref.visible != visible:
                pref.visible = visible
                pref.save(update_fields=["visible", "modificado_en"])
            continue
        PreferenciaKPI.objects.update_or_create(
            usuario=user, kpi_slug=slug, defaults={"visible": visible, "origen": "manual"},
        )

    # Tarjetas del header (zona hero) — checkboxes `hero_visible`.
    hero_marcados = set(request.POST.getlist("hero_visible"))
    for slug, _titulo, requiere_finanzas in HERO_DEFS:
        if requiere_finanzas and not _puede_finanzas(user):
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
    from .tablero import kpis_del_tablero

    user = request.user
    slugs = request.POST.getlist("slugs")
    if not slugs:
        return JsonResponse({"ok": False, "error": "Vacío."}, status=400)
    # Sólo se reordena lo que ya está en su tablero: un slug ajeno (o de un
    # KPI que no puede ver) no se cuela como «visible».
    suyos = {k.slug for k in kpis_del_tablero(user)}
    validos = [s for s in slugs if s in suyos]
    for i, slug in enumerate(validos):
        PreferenciaKPI.objects.update_or_create(
            usuario=user, kpi_slug=slug, defaults={"orden": i},
        )
    return JsonResponse({"ok": True, "n": len(validos)})


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
