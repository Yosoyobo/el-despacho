"""S-Geo-Picker-V1 — el geo-picker es dual-copy (regla §18).

El JS y el partial deben ser BYTE-idénticos en el-taller y la-gerencia, o el
comportamiento del selector de dirección diverge silenciosamente entre apps.
"""

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS = [
    "static/js/geo_picker.js",
    "templates/_componentes_tailadmin/_geo_picker.html",
]


@pytest.mark.parametrize("rel", ARCHIVOS)
def test_geo_picker_dual_copy_identico(rel):
    taller = (RAIZ / "el-taller" / rel).read_text()
    gerencia = (RAIZ / "la-gerencia" / rel).read_text()
    assert taller == gerencia, f"dual-copy desincronizado (§18): {rel}"
