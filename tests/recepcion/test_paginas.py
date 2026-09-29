"""Footer NoKo Devs (§4 #21) y legales (§4 #8) en TODA página de La Recepción,
dark mode propio (§4 #19) y la forma pública del portal."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.django_db

_NOKO = re.compile(
    r'Desarrollado por <a href="https://devs\.noko\.mx" target="_blank" rel="noopener"[^>]*>NoKo Devs</a>'
)


@pytest.fixture
def adentro(armar_cliente, acceso_de, entrar_como, client):
    d = armar_cliente("AAA", "ana@a.mx")
    d["acceso"] = acceso_de(d)
    entrar_como(d["acceso"])
    return d


def _rutas_con_sesion(d):
    return ["/", "/proyectos/", f"/proyectos/{d['proyecto'].codigo}/", "/cotizaciones/",
            f"/cotizaciones/{d['cotizacion'].pk}/", "/facturas/", f"/facturas/{d['factura'].pk}/",
            "/legal/privacidad", "/legal/terminos", "/no-existe/"]


def test_toda_pagina_con_sesion_lleva_el_footer_noko(client, adentro):
    for ruta in _rutas_con_sesion(adentro):
        r = client.get(ruta)
        assert r.status_code in (200, 404), ruta
        html = r.content.decode()
        assert _NOKO.search(html), f"{ruta} sin «Desarrollado por NoKo Devs»"
        assert 'href="/legal/privacidad"' in html and 'href="/legal/terminos"' in html


def test_las_paginas_publicas_tambien(client):
    for ruta in ("/entrar/", "/legal/privacidad", "/legal/terminos", "/entrar/token-que-no-existe/"):
        html = client.get(ruta).content.decode()
        assert _NOKO.search(html), ruta
    html = client.post("/entrar/", {"email": "x@y.mx"}).content.decode()
    assert _NOKO.search(html)


def test_los_legales_se_leen_sin_sesion_y_citan_la_lfpdppp(client):
    priv = client.get("/legal/privacidad")
    assert priv.status_code == 200
    assert "LFPDPPP" in priv.content.decode() and "ARCO" in priv.content.decode()
    term = client.get("/legal/terminos")
    assert term.status_code == 200 and "aviso de privacidad" in term.content.decode()


def test_ping_y_salud_son_publicos(client):
    assert client.get("/ping").content == b"ok"
    assert client.get("/salud").status_code in (200, 503)


def test_dark_mode_propio_antes_del_primer_pintado(client):
    html = client.get("/entrar/").content.decode()
    cabeza = html.split("</head>")[0]
    assert "localStorage.getItem('despacho-tema')" in cabeza
    assert cabeza.index("despacho-tema") < cabeza.index("tailwind.css")
    assert 'id="toggle-tema"' in html


def test_sin_chat_ni_chalan_ni_mensajes(client, adentro):
    """Oscar: «NO chat de cliente». El portal no tiene Chalán ni mensajería."""
    from django.urls import get_resolver

    rutas = " ".join(str(p.pattern) for p in get_resolver().url_patterns)
    for prohibido in ("chalan", "chat", "recado", "mensaje", "buzon"):
        assert prohibido not in rutas
    html = client.get("/").content.decode().lower()
    assert "chalán" not in html and "chalan" not in html


def test_el_css_compilado_trae_las_clases_del_portal():
    """El Tailwind commiteado es para correr en local; el del contenedor se
    compila en el build. Aun así tiene que estar al día con las plantillas."""
    css = (Path(__file__).resolve().parents[2] / "la-recepcion/static/css/tailwind.css").read_text()
    for clase in (".btn-primario", ".tarjeta", ".pestana-activa", ".chip", ".respira"):
        assert clase in css, clase
