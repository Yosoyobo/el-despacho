"""S-Mandados-V2 — geocoding gratis vía Nominatim. DEFENSIVO: nunca lanza."""

from __future__ import annotations

from lib import geocoding


def test_buscar_texto_corto_devuelve_vacio():
    assert geocoding.buscar("av") == []
    assert geocoding.buscar("") == []


def test_buscar_parsea_resultados(monkeypatch):
    class _Resp:
        status_code = 200
        @staticmethod
        def json():
            return [{
                "name": "Reforma 222", "display_name": "Reforma 222, CDMX",
                "lat": "19.4270", "lon": "-99.1677", "type": "building",
            }]

    monkeypatch.setattr(geocoding, "_cache", lambda: None)
    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp())
    res = geocoding.buscar("Reforma 222 CDMX")
    assert len(res) == 1
    assert res[0]["lat"] == 19.4270 and res[0]["lng"] == -99.1677
    assert res[0]["nombre"] == "Reforma 222"


def test_buscar_no_lanza_si_falla(monkeypatch):
    monkeypatch.setattr(geocoding, "_cache", lambda: None)
    import httpx
    def _boom(*a, **k):
        raise httpx.RequestError("down")
    monkeypatch.setattr(httpx, "get", _boom)
    assert geocoding.buscar("alguna direccion larga") == []


def test_identificar_coords_invalidas():
    assert geocoding.identificar(None, None) == {}
    assert geocoding.identificar("x", "y") == {}


def test_primer_resultado(monkeypatch):
    monkeypatch.setattr(geocoding, "buscar", lambda t, limite=1: [{"lat": 1.0, "lng": 2.0, "nombre": "X"}])
    assert geocoding.primer_resultado("algo")["lat"] == 1.0
    monkeypatch.setattr(geocoding, "buscar", lambda t, limite=1: [])
    assert geocoding.primer_resultado("nada") is None
