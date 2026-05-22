"""Helpers para series de ApexCharts: donut, area, barras.

Convierten querysets y diccionarios a JSON listos para `data-series='...'`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

# Paleta canónica (alineada con tokens TailAdmin del repo).
PALETA = [
    "#465fff",  # brand-500
    "#12b76a",  # success-500
    "#f79009",  # warning-500
    "#f04438",  # error-500
    "#7a5af8",  # purple-500
    "#0ba5ec",  # blue-light-500
    "#fb6514",  # orange-500
    "#ee46bc",  # pink
    "#0e9384",  # teal
    "#475467",  # gray-600
]

PALETA_ESTADOS = {
    "ok": "#12b76a",
    "exitoso": "#12b76a",
    "completada": "#12b76a",
    "entregado": "#12b76a",
    "activo": "#12b76a",
    "vigente": "#12b76a",
    "leido": "#12b76a",
    "respondido": "#0ba5ec",
    "pagado": "#12b76a",
    "error": "#f04438",
    "fallido": "#f04438",
    "cancelado": "#f04438",
    "vencido": "#f04438",
    "anulado": "#f04438",
    "warning": "#f79009",
    "en_pausa": "#f79009",
    "pendiente": "#f79009",
    "por_reembolsar": "#f79009",
    "nuevo": "#0ba5ec",
    "prospecto": "#0ba5ec",
    "por_cotizar": "#0ba5ec",
    "esperando_respuesta": "#7a5af8",
    "en_proceso_diseno": "#465fff",
    "en_proceso_produccion": "#fb6514",
    "en_revision": "#7a5af8",
    "archivado": "#475467",
    "sin_datos": "#d0d5dd",
    "no_configurada": "#98a2b3",
}


def _color_para(clave: str, idx: int = 0) -> str:
    return PALETA_ESTADOS.get(clave, PALETA[idx % len(PALETA)])


def _num(v: Any) -> float:
    """Convierte Decimal/None a float para JSON."""
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def donut_desde_conteo(conteo: dict[str, int | Decimal] | Iterable[tuple[str, Any]],
                       *,
                       etiquetas: dict[str, str] | None = None) -> str:
    """Convierte un diccionario `{clave: valor}` o iterable de tuplas
    `(clave, valor)` en JSON para un donut. Usa la paleta de estados
    cuando la clave coincide; si no, cicla la paleta general.

    `etiquetas` mapea clave → label legible (opcional).
    """
    pares = conteo.items() if isinstance(conteo, dict) else conteo
    out = []
    for i, (clave, val) in enumerate(pares):
        v = _num(val)
        if v <= 0:
            continue
        out.append({
            "label": (etiquetas or {}).get(clave, str(clave).replace("_", " ").capitalize()),
            "valor": v,
            "color": _color_para(str(clave), i),
        })
    return json.dumps(out)


def area_mensual(labels: list[str], series: list[dict[str, Any]]) -> str:
    """Convierte series mensuales (etiquetas categoría) a JSON multi-serie
    para un area chart. `series` es `[{name, data:[v,v,...], color?}]`."""
    out = {
        "labels": labels,
        "series": [
            {
                "name": s["name"],
                "data": [_num(x) for x in s.get("data", [])],
                "color": s.get("color") or PALETA[i % len(PALETA)],
            }
            for i, s in enumerate(series)
        ],
    }
    return json.dumps(out)


def serie_apex(puntos: list[tuple[Any, Any]], color: str | None = None) -> str:
    """Convierte una lista de tuplas `(x, y)` en JSON de serie ApexCharts."""
    data = [{"x": x, "y": _num(y)} for x, y in puntos]
    return json.dumps({"color": color or PALETA[0], "data": data})


def series_apex_multiple(grupos: list[tuple[str, list[tuple[Any, Any]]]]) -> str:
    """`grupos` es `[(nombre, [(x, y), ...]), ...]`."""
    out = []
    for i, (nombre, puntos) in enumerate(grupos):
        out.append({
            "name": nombre,
            "color": PALETA[i % len(PALETA)],
            "data": [{"x": x, "y": _num(y)} for x, y in puntos],
        })
    return json.dumps(out)


def kpi_color(tendencia: float | None) -> str:
    """Devuelve clase Tailwind para tendencia positiva/negativa."""
    if tendencia is None:
        return "text-gray-500"
    if tendencia > 0:
        return "text-success-600"
    if tendencia < 0:
        return "text-error-600"
    return "text-gray-500"
