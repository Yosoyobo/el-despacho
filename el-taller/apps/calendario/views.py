"""Vista de Calendario: mes actual + siguiente con tareas y entregas."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import eventos_por_dia, grid_mes


def _sumar_mes(year: int, month: int):
    if month == 12:
        return year + 1, 1
    return year, month + 1


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

    return render(request, "calendario/index.html", {
        "grid_actual": _enriquecer(grid_actual, eventos_actual),
        "grid_siguiente": _enriquecer(grid_siguiente, eventos_siguiente),
        "year": year,
        "month": month,
        "hoy": hoy,
        "nombre_mes_actual": _NOMBRES_MESES[month - 1],
        "nombre_mes_siguiente": _NOMBRES_MESES[m2 - 1],
        "year_siguiente": y2,
    })


_NOMBRES_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
