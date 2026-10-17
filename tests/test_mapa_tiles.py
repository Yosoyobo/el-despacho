"""Los mosaicos de los mapas salen de UN solo lugar y siempre llevan Referer.

Causa raíz del «403 Access blocked — App is not following the tile usage policy»
de OpenStreetMap (ticket del mapa de Geocerca): Django manda por defecto
`Referrer-Policy: same-origin`; con ésa el navegador no envía Referer al pedir
mosaicos a otro origen, y OSM bloquea los clientes sin Referer. Arreglo: la
política del sitio pasa a `strict-origin-when-cross-origin` y cada capa de
mosaicos declara `referrerPolicy: 'origin'`, creada sólo desde `mapa_tiles.js`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
APPS = ("el-taller", "la-gerencia")
FUENTES = ("*.html", "*.js")
CENTRAL = "mapa_tiles.js"


def _archivos_de_mapa():
    for app in APPS:
        for patron in FUENTES:
            for ruta in (RAIZ / app).rglob(patron):
                partes = set(ruta.parts)
                if "vendor" in partes or "node_modules" in partes or "staticfiles" in partes:
                    continue
                if ruta.name == CENTRAL:
                    continue
                yield ruta


def test_mapa_tiles_dual_copy_identico():
    rel = f"static/js/{CENTRAL}"
    assert (RAIZ / "el-taller" / rel).read_text() == (RAIZ / "la-gerencia" / rel).read_text()


def test_la_fabrica_central_fija_referrer_policy():
    js = (RAIZ / "el-taller" / "static" / "js" / CENTRAL).read_text()
    assert re.search(r"referrerPolicy:\s*[\"']origin[\"']", js)
    assert "tile.openstreetmap.org" in js


def test_nadie_crea_un_tilelayer_suelto():
    """Ningún mapa arma su capa a mano: sin `referrerPolicy` volvería el 403."""
    sueltos = []
    for ruta in _archivos_de_mapa():
        texto = ruta.read_text(errors="ignore")
        if re.search(r"L\.tileLayer\s*\(", texto) or "tile.openstreetmap.org" in texto:
            sueltos.append(str(ruta.relative_to(RAIZ)))
    assert not sueltos, (
        "Usa `despachoTileLayer()` (static/js/mapa_tiles.js) en vez de L.tileLayer: " + ", ".join(sueltos)
    )


@pytest.mark.parametrize("app", APPS)
def test_base_carga_mapa_tiles_antes_que_el_geo_picker(app):
    base = (RAIZ / app / "templates" / "base.html").read_text()
    assert "js/mapa_tiles.js" in base
    assert base.index("js/mapa_tiles.js") < base.index("js/geo_picker.js")


@pytest.mark.parametrize("app", APPS)
def test_la_politica_de_referrer_del_sitio_permite_el_origen(app):
    carpeta = "el_taller" if app == "el-taller" else "la_gerencia"
    settings = (RAIZ / app / carpeta / "settings.py").read_text()
    assert 'SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"' in settings
