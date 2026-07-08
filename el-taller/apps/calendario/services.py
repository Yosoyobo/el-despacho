"""Construye el grid del calendario para vista mes y mini-cal del home.

No hay modelo propio — el Calendario lee tareas y proyectos visibles para
el usuario y los emplaca en celdas por día.
"""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta

from django.utils import timezone


def _proyectos_visibles_qs(user):
    from apps.los_proyectos.models import Proyecto

    from lib.permisos import roles_efectivos

    # V6 Bloque 10: roles efectivos (rol primario + roles_extra) en lugar de
    # user.rol duro — un "miembro" con rol personalizado "dueno" ve lo mismo.
    roles = roles_efectivos(user)
    qs = Proyecto.activos.select_related("cliente")  # LC 2026-07: sin archivados
    if roles & {"super_admin", "dueno", "contador"}:
        return qs
    if "disenador" in roles:
        return qs.filter(asignaciones__usuario=user).distinct()
    return Proyecto.objects.none()


def _tareas_visibles_qs(user):
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.models import ProyectoAsignacion

    from lib.permisos import roles_efectivos

    # V6 Bloque 10: restringe a sus proyectos solo si es diseñador (primario
    # o personalizado) sin un rol amplio que le dé visibilidad total.
    roles = roles_efectivos(user)
    qs = Tarea.objects.exclude(estado="completada").select_related("proyecto", "asignada_a")
    if "disenador" in roles and not (roles & {"super_admin", "dueno", "contador"}):
        proyectos_ids = ProyectoAsignacion.objects.filter(usuario=user).values_list("proyecto_id", flat=True)
        qs = qs.filter(proyecto_id__in=list(proyectos_ids))
    return qs


def eventos_por_dia(user, inicio: date, fin: date) -> dict[date, list[dict]]:
    """Devuelve un dict {fecha: [{tipo, titulo, url, color}]} para el rango.

    Regla de color: si el día del evento YA PASÓ (anterior a hoy), el color
    siempre es "gray" sin importar la categoría — así los eventos vencidos se
    apagan visualmente en TODOS los calendarios (página + mini-cal del home).
    """
    eventos: dict[date, list[dict]] = defaultdict(list)
    hoy = timezone.localdate()

    # C6 S-LC-Feedback-V6: Proyecto.fecha_compromiso ahora es datetime → se
    # filtra y agrupa por su componente de fecha (`__date` / .date()).
    for p in _proyectos_visibles_qs(user).filter(
        fecha_compromiso__date__gte=inicio, fecha_compromiso__date__lte=fin
    ):
        dia_evento = timezone.localtime(p.fecha_compromiso).date()
        eventos[dia_evento].append({
            "tipo": "entrega",
            "titulo": p.nombre,
            "subtitulo": p.cliente.razon_social,
            "url": f"/proyectos/{p.pk}/",
            "color": "gray" if dia_evento < hoy else "brand",
        })

    # V6 Bloque 2: el tipo de la tarea (Entrega/Junta/Recoger) se refleja en
    # el calendario con emoji + hora si existe.
    _emoji = {"entrega": "📦", "junta": "📅", "recoger": "🚚"}
    for t in _tareas_visibles_qs(user).filter(
        fecha_compromiso__gte=inicio, fecha_compromiso__lte=fin
    ):
        pre = _emoji.get(t.tipo)
        hora = t.hora.strftime("%H:%M") + " · " if t.hora else ""
        color = "gray" if t.fecha_compromiso < hoy else ("warning" if t.prioridad == "alta" else "gray")
        eventos[t.fecha_compromiso].append({
            "tipo": "tarea",
            "tipo_tarea": t.tipo,
            "titulo": f"{pre} {hora}{t.titulo}" if pre else f"{hora}{t.titulo}",
            "subtitulo": t.proyecto.codigo,
            "url": f"/tareas/{t.pk}/",
            "color": color,
            "estado": t.estado,
        })

    # S-LC-Feedback-V13: eventos genéricos (feriados, vacaciones, operativos).
    # No ligados a proyecto; visibles para todo el Taller. Multi-día: se pinta
    # un chip en CADA día de su rango dentro de la ventana.
    from apps.el_pizarron.models import Evento
    for ev in Evento.objects.filter(fecha_inicio__lte=fin, fecha_fin__gte=inicio):
        d = max(ev.fecha_inicio, inicio)
        ultimo = min(ev.fecha_fin, fin)
        while d <= ultimo:
            eventos[d].append({
                "tipo": "evento",
                "titulo": ev.titulo,
                "subtitulo": "",
                "url": f"/calendario/evento/{ev.pk}/",
                "color_hex": ev.color,
                "es_multidia": ev.es_multidia,
                "es_inicio": d == ev.fecha_inicio,
                "es_fin": d == ev.fecha_fin,
                "evento_id": ev.pk,
            })
            d += timedelta(days=1)

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
