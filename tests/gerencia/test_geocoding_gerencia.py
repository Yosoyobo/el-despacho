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


def test_sede_form_tiene_buscador(client, usuario_factory):
    """El form de Sede renderiza el input de búsqueda de dirección."""
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/catalogos/sedes/nueva/")
    assert resp.status_code == 200
    assert b'id="sede-buscar"' in resp.content
    assert b"/gerencia/geocoding" in resp.content
