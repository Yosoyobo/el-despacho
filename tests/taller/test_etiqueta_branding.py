"""La tarjeta de producto del proyecto dice «Branding», no «Impresión» (decisión
de Oscar, 14-oct-2026). Sólo cambia la etiqueta visible: el tipo interno
`impresion`, el Catálogo y los PDFs de cotización no se tocan.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TPL = Path(__file__).resolve().parents[2] / "el-taller" / "templates" / "proyectos"


@pytest.mark.parametrize("archivo", ["_producto_card.html", "_escala_fila.html", "_form_productos_js.html"])
def test_la_etiqueta_visible_es_branding(archivo):
    texto = (TPL / archivo).read_text(encoding="utf-8")
    assert "Branding" in texto
    for viejo in (">Impresión<", "— Sin impresión —", "Quitar impresión", "eti('Impresión')",
                  "Costo de impresión"):
        assert viejo not in texto, (archivo, viejo)


def test_el_tipo_interno_no_se_renombro():
    js = (TPL / "_form_productos_js.html").read_text(encoding="utf-8")
    assert "tipo: 'impresion'" in js
    assert "p.tipo === 'impresion'" in js
