"""Vista de Calendario: mes actual + siguiente con tareas y entregas."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from .services import eventos_por_dia, grid_mes


def _sumar_mes(year: int, month: int):
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _restar_mes(year: int, month: int):
    if month == 1:
        return year - 1, 12
    return year, month - 1


@login_required
def calendario(request):
    hoy = date.today()
    try:
        year = int(request.GET.get("year") or hoy.year)
        month = int(request.GET.get("month") or hoy.month)
    except (TypeError, ValueError):
        year, month = hoy.year, hoy.month

    grid_actual = grid_mes(year, month)
    y2, m2 = _sumar_mes(year, month)
    grid_siguiente = grid_mes(y2, m2)

    eventos_actual = eventos_por_dia(request.user, grid_actual["inicio"], grid_actual["fin"])
    eventos_siguiente = eventos_por_dia(request.user, grid_siguiente["inicio"], grid_siguiente["fin"])

    # Pre-mezcla eventos en cada celda para iteración sin lookup en template.
    def _enriquecer(grid, evmap):
        for semana in grid["semanas"]:
            for celda in semana:
                celda["eventos"] = evmap.get(celda["fecha"], [])
        return grid

    # Lista de eventos a partir de hoy (90 días) para la columna derecha.
    proximos = proximos_eventos(request)

    # Navegación
    y_prev, m_prev = _restar_mes(year, month)
    y_next, m_next = _sumar_mes(year, month)

    return render(request, "calendario/index.html", {
        "grid_actual": _enriquecer(grid_actual, eventos_actual),
        "grid_siguiente": _enriquecer(grid_siguiente, eventos_siguiente),
        "year": year,
        "month": month,
        "hoy": hoy,
        "nombre_mes_actual": _NOMBRES_MESES[month - 1],
        "nombre_mes_siguiente": _NOMBRES_MESES[m2 - 1],
        "year_siguiente": y2,
        "proximos_eventos": proximos,
        "nav": {
            "prev_url": f"?year={y_prev}&month={m_prev}",
            "next_url": f"?year={y_next}&month={m_next}",
            "hoy_url": "?",
        },
        "meses": _NOMBRES_MESES,
    })


_NOMBRES_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


@login_required
def dia_popover(request, fecha_iso: str):
    """GET /calendario/dia/<YYYY-MM-DD>/ — modal HTMX con eventos del día.

    Usado por el mini-calendario del Dashboard: click en un día con eventos
    inyecta este partial en #modal-slot.
    """
    try:
        f = datetime.strptime(fecha_iso, "%Y-%m-%d").date()
    except ValueError as e:
        raise Http404("fecha inválida") from e
    eventos = eventos_por_dia(request.user, f, f).get(f, [])
    nombre = f.strftime("%d") + " " + _NOMBRES_MESES[f.month - 1] + f" {f.year}"
    return render(request, "calendario/_modal_dia.html", {
        "fecha": f,
        "fecha_etiqueta": nombre,
        "eventos": eventos,
    })


@login_required
def nuevo_evento_modal(request):
    """GET /calendario/nuevo/ — modal HTMX con dos opciones (Tarea o Proyecto).

    Decisión S-LC-Feedback-V2: no creamos modelo Evento — reusamos Tarea
    y Proyecto existentes. El modal redirige al form correspondiente con
    la fecha pre-cargada si viene en la querystring.
    """
    fecha_default = request.GET.get("fecha") or ""
    return render(request, "calendario/_modal_nuevo_evento.html", {
        "fecha_default": fecha_default,
    })


def proximos_eventos(request):
    """Lista de tareas/entregas desde hoy en adelante (para la página Calendario)."""
    hoy = date.today()
    fin = hoy + timedelta(days=90)  # ventana de 90 días para no inflar el render
    evs = eventos_por_dia(request.user, hoy, fin)
    items = []
    for f in sorted(evs.keys()):
        for ev in evs[f]:
            items.append({**ev, "fecha": f})
    return items
