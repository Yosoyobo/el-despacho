"""S-Geo-Picker-V1 — selector de dirección/ubicación unificado (El Taller).

Cuadro de resultados en vivo (POIs internos + Nominatim) + auto-pin del mapa.
Verifica el endpoint compartido `/geo/buscar`, los POIs internos (buscar_pois),
el partial canónico en sus dos modos y que el JS se carga. Nada pega a Nominatim
(se mockea `lib.geocoding`).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


# ───────────────────────── endpoint /geo/buscar ─────────────────────────

def test_endpoint_devuelve_pois_y_resultados(client, usuario_factory, monkeypatch):
    from apps.el_pizarron import poi

    from lib import geocoding
    monkeypatch.setattr(geocoding, "buscar", lambda q, limite=6: [
        {"nombre": "Calle 1", "direccion": "Calle 1, CDMX", "lat": 19.4, "lng": -99.1, "tipo": "road"},
    ])
    monkeypatch.setattr(poi, "buscar_pois", lambda q="", limite=8: [
        {"label": "Sede Centro", "lat": 19.43, "lng": -99.13, "fuente": "sede", "clave": "sede:1"},
    ])
    client.force_login(usuario_factory(rol="super_admin"))
    data = client.get("/geo/buscar?q=centro").json()
    assert data["pois"][0]["label"] == "Sede Centro"
    assert data["resultados"][0]["lat"] == 19.4


def test_endpoint_pois_cero_no_consulta_pois(client, usuario_factory, monkeypatch):
    from apps.el_pizarron import poi

    from lib import geocoding
    monkeypatch.setattr(geocoding, "buscar", lambda q, limite=6: [])

    def _boom(*a, **k):  # si se llamara con pois=0, reventaría el test
        raise AssertionError("buscar_pois no debe llamarse con pois=0")

    monkeypatch.setattr(poi, "buscar_pois", _boom)
    client.force_login(usuario_factory(rol="super_admin"))
    data = client.get("/geo/buscar?q=centro&pois=0").json()
    assert data["pois"] == []


def test_endpoint_reverse_identifica_punto(client, usuario_factory, monkeypatch):
    from lib import geocoding
    monkeypatch.setattr(geocoding, "identificar", lambda lat, lng: {"nombre": "X", "direccion": "X, CDMX"})
    client.force_login(usuario_factory(rol="super_admin"))
    data = client.get("/geo/buscar?lat=19.4&lng=-99.1").json()
    assert data["punto"]["nombre"] == "X"


def test_endpoint_nominatim_caido_no_revienta(client, usuario_factory, monkeypatch):
    from apps.el_pizarron import poi

    from lib import geocoding
    monkeypatch.setattr(geocoding, "buscar", lambda q, limite=6: [])  # como si fallara
    monkeypatch.setattr(poi, "buscar_pois", lambda q="", limite=8: [])
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/geo/buscar?q=loquesea")
    assert resp.status_code == 200
    assert resp.json() == {"pois": [], "resultados": []}


def test_endpoint_requiere_login(client):
    assert client.get("/geo/buscar?q=reforma").status_code in (301, 302)


# ───────────────────────── buscar_pois (POIs internos) ─────────────────────────

def test_buscar_pois_filtra_por_texto_sin_acentos(monkeypatch):
    from apps.el_pizarron import poi
    monkeypatch.setattr(poi, "pois_para_destino", lambda: [
        {"label": "Almacén Sur", "lat": 1, "lng": 2, "fuente": "sede", "clave": "sede:1"},
        {"label": "Bodega Norte", "lat": 3, "lng": 4, "fuente": "sede", "clave": "sede:2"},
    ])
    assert [p["label"] for p in poi.buscar_pois("almacen")] == ["Almacén Sur"]  # ignora acentos
    assert len(poi.buscar_pois("")) == 2  # sin texto → todos


def test_buscar_pois_defensivo(monkeypatch):
    from apps.el_pizarron import poi

    def _boom():
        raise RuntimeError("DB caída")

    monkeypatch.setattr(poi, "pois_para_destino", _boom)
    assert poi.buscar_pois("x") == []  # nunca tumba el endpoint


# ───────────────────────── partial _geo_picker.html ─────────────────────────

def test_partial_modo_texto():
    from django.template.loader import render_to_string
    html = render_to_string("_componentes_tailadmin/_geo_picker.html", {
        "modo": "texto", "objetivo_texto": "id_direccion", "con_pois": False,
    })
    assert "data-geo-picker" in html
    assert 'data-modo="texto"' in html
    assert 'data-objetivo-texto="id_direccion"' in html
    assert 'data-con-pois="0"' in html
    assert "data-geo-mapa" not in html  # modo texto no dibuja mapa


def test_partial_modo_completo():
    from django.template.loader import render_to_string
    html = render_to_string("_componentes_tailadmin/_geo_picker.html", {
        "modo": "completo", "lat_id": "id_lat", "lng_id": "id_lng",
        "etiqueta_id": "id_etiq", "con_geoloc": True, "con_pois": True, "mapa_abierto": True,
    })
    assert 'data-modo="completo"' in html
    assert 'data-lat-input="id_lat"' in html
    assert 'data-lng-input="id_lng"' in html
    assert 'data-etiqueta-input="id_etiq"' in html
    assert 'data-con-pois="1"' in html
    assert "data-geo-mapa" in html
    assert "data-geo-localizar" in html
    assert "data-geo-toggle-mapa" in html


# ───────────────────────── integración en pantallas ─────────────────────────

def test_base_carga_geo_picker_js(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"geo_picker.js" in resp.content


def test_modal_mandado_usa_picker(client, proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Mandado, Tarea
    p = proyecto_factory(estado="en_proceso_diseno")
    t = Tarea.objects.create(proyecto=p, titulo="Entregar", tipo="entrega", estado="pendiente")
    m = Mandado.objects.get(tarea=t)
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/mandados/{m.pk}/destino")
    assert resp.status_code == 200
    assert b"data-geo-picker" in resp.content
    assert b'data-modo="completo"' in resp.content
    assert b'data-lat-input="md-lat"' in resp.content


def test_cliente_form_tiene_picker(client, usuario_factory):
    from django.urls import reverse
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(reverse("cartera-nuevo"))
    assert resp.status_code == 200
    assert b"data-geo-picker" in resp.content
    assert b'data-objetivo-texto="id_direccion"' in resp.content
