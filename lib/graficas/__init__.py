"""lib.graficas — helpers reusables para alimentar ApexCharts desde Django.

Los views llaman a estos helpers, serializan a JSON y los templates lo
pintan vía `data-chart="..."` + `data-series='...'`. El JS que pinta es
`<app>/static/js/site_charts.js` (idéntico en La Gerencia y El Taller —
patrón "dos copias sincronizadas" del repo).
"""

from .series import (
    PALETA,
    area_mensual,
    donut_desde_conteo,
    serie_apex,
    series_apex_multiple,
)

__all__ = [
    "PALETA",
    "area_mensual",
    "donut_desde_conteo",
    "serie_apex",
    "series_apex_multiple",
]
