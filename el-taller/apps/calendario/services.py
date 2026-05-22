"""Construye el grid del calendario para vista mes y mini-cal del home.

No hay modelo propio — el Calendario lee tareas y proyectos visibles para
el usuario y los emplaca en celdas por día.
"""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta


def _proyectos_visibles_qs(user):
    from apps.los_proyectos.models import Proyecto

    rol = getattr(user, "rol", None)
    qs = Proyecto.objects.select_related("cliente")
    if rol in ("super_admin", "dueno", "contador"):
        return qs
    if rol == "disenador":
        return qs.filter(asignaciones__usuario=user).distinct()
    return Proyecto.objects.none()


def _tareas_visibles_qs(user):
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.models import ProyectoAsignacion

    rol = getattr(user, "rol", None)
    qs = Tarea.objects.exclude(estado="completada").select_related("proyecto", "asignada_a")
    if rol == "disenador":
        proyectos_ids = ProyectoAsignacion.objects.filter(usuario=user).values_list("proyecto_id", flat=True)
        qs = qs.filter(proyecto_id__in=list(proyectos_ids))
    return qs


def eventos_por_dia(user, inicio: date, fin: date) -> dict[date, list[dict]]:
    """Devuelve un dict {fecha: [{tipo, titulo, url, color}]} para el rango."""
    eventos: dict[date, list[dict]] = defaultdict(list)

    for p in _proyectos_visibles_qs(user).filter(
        fecha_compromiso__gte=inicio, fecha_compromiso__lte=fin
    ):
        eventos[p.fecha_compromiso].append({
            "tipo": "entrega",
            "titulo": p.nombre,
            "subtitulo": p.cliente.razon_social,
            "url": f"/proyectos/{p.pk}/",
            "color": "brand",
        })

    for t in _tareas_visibles_qs(user).filter(
        fecha_compromiso__gte=inicio, fecha_compromiso__lte=fin
    ):
        eventos[t.fecha_compromiso].append({
            "tipo": "tarea",
            "titulo": t.titulo,
            "subtitulo": t.proyecto.codigo,
            "url": f"/tareas/{t.pk}/",
            "color": "warning" if t.prioridad == "alta" else "gray",
        })

    return eventos


def grid_mes(year: int, month: int) -> dict:
    """Devuelve estructura de filas-semana × 7 días para renderizar el mes.

    Cada celda: {fecha, mes_actual (bool), es_finde (bool)}.
    """
    primer_dia, dias_en_mes = monthrange(year, month)
    # primer_dia: 0=lunes, 6=domingo (calendar usa lunes-first por default).
    inicio = date(year, month, 1) - timedelta(days=primer_dia)
    semanas = []
    cursor = inicio
    while True:
        semana = []
        for _ in range(7):
            semana.append({
                "fecha": cursor,
                "mes_actual": cursor.month == month,
                "es_finde": cursor.weekday() >= 5,
                "es_hoy": cursor == date.today(),
            })
            cursor += timedelta(days=1)
        semanas.append(semana)
        if cursor.month != month and cursor > date(year, month, dias_en_mes):
            break
        if len(semanas) >= 6:
            break
    return {"year": year, "month": month, "semanas": semanas, "inicio": inicio, "fin": cursor - timedelta(days=1)}


def datos_mini_cal(user, year: int, month: int) -> dict:
    """Mini-calendario para el home. Marca con puntito los días que tienen eventos."""
    grid = grid_mes(year, month)
    eventos = eventos_por_dia(user, grid["inicio"], grid["fin"])
    dias_con_eventos = {fecha for fecha, evs in eventos.items() if evs}
    return {
        "grid": grid,
        "dias_con_eventos": dias_con_eventos,
        "total_eventos": sum(len(v) for v in eventos.values()),
    }
