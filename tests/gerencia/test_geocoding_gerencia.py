"""S-Geocoding-Gerencia — buscador de dirección con autocompletado en los mapas
interactivos de La Gerencia (sede_form, directorio _tab_datos). Endpoint proxy a
Nominatim espejo del de El Taller, porque los Django projects no comparten urlconf.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def test_geocoding_requiere_login(client):
    resp = client.get("/gerencia/geocoding?q=Reforma 222")
    # login_required → redirige al login (302) en lugar de servir resultados.
    assert resp.status_code in (302, 301)


def test_geocoding_busca_por_texto(client, usuario_factory, monkeypatch):
    from lib import geocoding
    monkeypatch.setattr(
        geocoding, "buscar",
        lambda q, limite=6: [{"nombre": "Reforma 222", "direccion": "Reforma 222, CDMX",
                              "lat": 19.427, "lng": -99.1677, "tipo": "building"}],
    )
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/gerencia/geocoding?q=Reforma 222 CDMX")
    assert resp.status_code == 200
    data = resp.json()
    assert "resultados" in data and len(data["resultados"]) == 1
    assert data["resultados"][0]["lat"] == 19.427


def test_geocoding_identifica_punto(client, usuario_factory, monkeypatch):
    from lib import geocoding
    monkeypatch.setattr(
        geocoding, "identificar",
        lambda lat, lng: {"nombre": "Centro", "direccion": "Centro, CDMX"},
    )
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/gerencia/geocoding?lat=19.4326&lng=-99.1332")
    assert resp.status_code == 200
    assert resp.json()["punto"]["nombre"] == "Centro"


def test_geocoding_incluye_pois_de_sedes(client, usuario_factory, monkeypatch):
    """El cuadro de resultados en vivo trae POIs (sedes activas con pin)."""
    from apps.checador.models.sede import SedeLC

    from lib import geocoding
    monkeypatch.setattr(geocoding, "buscar", lambda q, limite=6: [])
    SedeLC.objects.create(nombre="Oficina Centro", lat="19.43", lng="-99.13", activa=True)
    SedeLC.objects.create(nombre="Bodega Norte", lat="19.50", lng="-99.20", activa=True)
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    data = client.get("/geo/buscar?q=centro").json()
    etiquetas = [p["label"] for p in data["pois"]]
    assert etiquetas == ["Oficina Centro"]  # filtra por texto (sin acentos)
    assert data["pois"][0]["fuente"] == "sede"


def test_geocoding_pois_cero_omite_sedes(client, usuario_factory, monkeypatch):
    from apps.checador.models.sede import SedeLC

    from lib import geocoding
    monkeypatch.setattr(geocoding, "buscar", lambda q, limite=6: [])
    SedeLC.objects.create(nombre="Oficina Centro", lat="19.43", lng="-99.13", activa=True)
    client.force_login(usuario_factory(rol="super_admin"))
    data = client.get("/geo/buscar?q=centro&pois=0").json()
    assert data["pois"] == []


def test_directorio_tab_datos_tiene_picker(client, usuario_factory):
    """El tab Datos del Directorio usa el geo-picker para la geocerca."""
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    empleado = usuario_factory(rol="disenador")
    client.force_login(admin)
    resp = client.get(reverse("directorio-panel-datos", args=[empleado.pk]))
    assert resp.status_code == 200
    assert b"data-geo-picker" in resp.content
    assert b'data-lat-input="id_geo_lat"' in resp.content


def test_sede_form_tiene_buscador(client, usuario_factory):
    """El form de Sede renderiza el geo-picker (cuadro de resultados + mapa)."""
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/catalogos/sedes/nueva/")
    assert resp.status_code == 200
    assert b"data-geo-picker" in resp.content
    assert b"data-geo-buscar" in resp.content
    assert b"/geo/buscar" in resp.content
