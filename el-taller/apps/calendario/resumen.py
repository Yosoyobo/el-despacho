"""Resumen ejecutivo del calendario (LC 2026-07-29).

Oscar pidió un resumen **muy resumido** y con un formato exacto:

    Hoy: [eventos de hoy]

    Esta semana: [eventos lun-vie de esta semana, sin los que ya pasaron
                 —hoy sí cuenta—]
    Tareas: [tareas por orden, sin las marcadas completadas]
    Siguientes entregas: [por orden, «fecha · proyecto · productos»]

El formato no tiene nada que interpretar, así que las cuatro secciones se arman
**con consultas, no con IA**: sale exacto, instantáneo y gratis (mismo criterio
que el reporte de pendientes del Dashboard). El Chalán se queda con lo único que
sí requiere criterio — una línea de lectura de la carga — y si no responde, las
secciones se muestran igual.

Respeta permisos: todo sale de `services.eventos_por_dia` /
`_proyectos_visibles_qs`, que ya filtran por lo que el usuario puede ver.
"""

from __future__ import annotations

from datetime import date, timedelta

# Tope por sección: un resumen «muy resumido» no puede tener 80 renglones.
LIMITE_SECCION = 12

# Ventana de las entregas siguientes (las de esta semana ya salen arriba).
DIAS_ENTREGAS = 60


def _dia_legible(d: date, hoy: date) -> str:
    """«hoy», «mañana» o «vie 31 jul» — corto, para leer de un golpe."""
    if d == hoy:
        return "hoy"
    if d == hoy + timedelta(days=1):
        return "mañana"
    dias = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
    meses = ("ene", "feb", "mar", "abr", "may", "jun",
             "jul", "ago", "sep", "oct", "nov", "dic")
    return f"{dias[d.weekday()]} {d.day} {meses[d.month - 1]}"


def _texto_evento(ev: dict) -> str:
    """Título del evento sin el emoji ni la hora repetida: ya viene formateado
    desde `eventos_por_dia`, así que se usa tal cual + su subtítulo."""
    titulo = (ev.get("titulo") or "").strip()
    sub = (ev.get("subtitulo") or "").strip()
    return f"{titulo} — {sub}" if sub else titulo


def _productos_de(proyecto) -> str:
    """Productos que se entregan, por su nombre en ESTE proyecto (el alias manda)."""
    try:
        nombres = [pp.nombre_visible for pp in proyecto.productos_incluidos]
    except Exception:  # noqa: BLE001 — un proyecto raro no tumba el resumen
        return ""
    if not nombres:
        return ""
    if len(nombres) > 4:
        return ", ".join(nombres[:4]) + f" y {len(nombres) - 4} más"
    return ", ".join(nombres)


def secciones_calendario(usuario) -> list[dict]:
    """Las cuatro secciones del resumen, en el orden que pidió Oscar.

    Devuelve `[{titulo, lineas}]`; las secciones vacías se omiten salvo «Hoy»,
    que siempre sale (que no haya nada hoy es información).
    """
    from django.utils import timezone

    from .services import _proyectos_visibles_qs, eventos_por_dia

    hoy = timezone.localdate()
    # Lunes a viernes de la semana en curso, desde hoy (lo que ya pasó no entra;
    # hoy sí, tal como lo pidió Oscar).
    lunes = hoy - timedelta(days=hoy.weekday())
    viernes = lunes + timedelta(days=4)
    fin_semana_habil = max(viernes, hoy)

    por_dia = eventos_por_dia(usuario, hoy, fin_semana_habil)

    # ── Hoy ──────────────────────────────────────────────────────────────
    hoy_lineas = [_texto_evento(ev) for ev in por_dia.get(hoy, [])]

    # ── Esta semana (lun-vie, de mañana al viernes) ───────────────────────
    semana_lineas: list[str] = []
    dia = hoy + timedelta(days=1)
    while dia <= viernes:
        for ev in por_dia.get(dia, []):
            semana_lineas.append(f"{_dia_legible(dia, hoy)}: {_texto_evento(ev)}")
        dia += timedelta(days=1)

    # ── Tareas (sin completadas, por fecha) ───────────────────────────────
    tareas_lineas: list[str] = []
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    terminales = slugs_terminales_tarea()
    from apps.el_pizarron.views import _tareas_visibles
    tareas = (
        _tareas_visibles(usuario)
        .filter(archivada=False)
        .exclude(estado__in=terminales)
        .order_by("fecha_compromiso", "pk")
        .distinct()[: LIMITE_SECCION + 1]
    )
    for t in tareas:
        cuando = _dia_legible(t.fecha_compromiso, hoy) if t.fecha_compromiso else "sin fecha"
        quien = ""
        if t.asignada_a_id:
            quien = f" ({t.asignada_a.nombre_completo or t.asignada_a.email})"
        tareas_lineas.append(f"{cuando}: {t.titulo}{quien}")

    # ── Siguientes entregas («fecha · proyecto · productos») ───────────────
    entregas_lineas: list[str] = []
    proyectos = (
        _proyectos_visibles_qs(usuario)
        .filter(fecha_compromiso__date__gte=hoy,
                fecha_compromiso__date__lte=hoy + timedelta(days=DIAS_ENTREGAS))
        .order_by("fecha_compromiso")[: LIMITE_SECCION + 1]
    )
    for p in proyectos:
        cuando = _dia_legible(timezone.localtime(p.fecha_compromiso).date(), hoy)
        productos = _productos_de(p)
        nombre = p.nombre or p.codigo
        entregas_lineas.append(f"{cuando} · {nombre}" + (f" · {productos}" if productos else ""))

    secciones = [{"titulo": "Hoy", "lineas": hoy_lineas or ["Nada agendado."]}]
    for titulo, lineas in (
        ("Esta semana", semana_lineas),
        ("Tareas", tareas_lineas),
        ("Siguientes entregas", entregas_lineas),
    ):
        if lineas:
            secciones.append({"titulo": titulo, "lineas": lineas[:LIMITE_SECCION]})
    return secciones


def texto_calendario(usuario) -> str:
    """Las secciones en texto plano (para el prompt del Chalán y para copiar)."""
    partes: list[str] = []
    for sec in secciones_calendario(usuario):
        partes.append(f"{sec['titulo']}:")
        partes += [f"- {ln}" for ln in sec["lineas"]]
        partes.append("")
    return "\n".join(partes).strip()


__all__ = ["secciones_calendario", "texto_calendario", "LIMITE_SECCION"]
