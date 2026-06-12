"""Export CSV de El Checador (E6) — mismo patrón que tesoreria/exports.py.

- UTF-8 con BOM para Excel.
- Fechas ISO 8601, horas HH:MM.
- Encabezados en español. Booleanos como Sí/No.
"""

from __future__ import annotations

import csv
from datetime import date

from django.http import HttpResponse

from .models import Jornada, SesionProyecto

VISTAS = ("jornadas", "sesiones")

ENCABEZADOS: dict[str, list[str]] = {
    "jornadas": [
        "Usuario", "Email", "Fecha", "Entrada", "Salida", "Horas",
        "Retardo (min)", "Sin ubicación (entrada)", "Sin ubicación (salida)", "Estado",
    ],
    "sesiones": [
        "Usuario", "Email", "Proyecto", "Inicio", "Fin", "Duración (min)", "Origen", "Nota",
    ],
}


def _hms(v) -> str:
    return v.strftime("%H:%M") if v else ""


def _dt(v) -> str:
    return v.strftime("%Y-%m-%d %H:%M") if v else ""


def _bool(v) -> str:
    return "Sí" if v else "No"


def _rango(params):
    return params.get("desde") or "", params.get("hasta") or ""


def filas_para(vista: str, params: dict):
    encabezados = ENCABEZADOS[vista]
    desde, hasta = _rango(params)
    filas = []

    if vista == "jornadas":
        qs = Jornada.objects.select_related("usuario").order_by("fecha", "usuario_id")
        if desde:
            qs = qs.filter(fecha__gte=desde)
        if hasta:
            qs = qs.filter(fecha__lte=hasta)
        for j in qs:
            filas.append([
                j.usuario.nombre_completo or "", j.usuario.email, j.fecha.isoformat(),
                _hms(j.entrada_en), _hms(j.salida_en),
                j.horas_trabajadas if j.horas_trabajadas is not None else "",
                j.retardo_min, _bool(j.entrada_sin_geo), _bool(j.salida_sin_geo), j.estado,
            ])
    else:  # sesiones
        qs = SesionProyecto.objects.select_related("usuario", "proyecto").filter(estado="cerrada").order_by("inicio")
        if desde:
            qs = qs.filter(inicio__date__gte=desde)
        if hasta:
            qs = qs.filter(inicio__date__lte=hasta)
        for s in qs:
            filas.append([
                s.usuario.nombre_completo or "", s.usuario.email,
                s.proyecto.codigo if s.proyecto_id else "",
                _dt(s.inicio), _dt(s.fin), s.duracion_min or 0, s.get_origen_display(), s.nota,
            ])

    return encabezados, filas


def responder_csv(vista: str, params: dict):
    encabezados, filas = filas_para(vista, params)
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    nombre = f"checador_{vista}_{date.today().isoformat()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{nombre}"'
    response.write("﻿")  # BOM para Excel
    writer = csv.writer(response)
    writer.writerow(encabezados)
    for f in filas:
        writer.writerow(f)
    return response, len(filas)
