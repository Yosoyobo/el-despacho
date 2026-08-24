"""Distancias por calles reales (S-NUC-Servicios, 2026-08-24).

Lo que cuidan estas pruebas, en orden de lo que dolería:

1. **El orden de las coordenadas.** El repo entero habla (lat, lng) y OSRM pide
   (lng, lat). Invertirlas manda a Texas una ruta de la Ciudad de México — y no
   da error: **da una ruta**, con kilómetros y minutos creíbles. Es el fallo más
   caro posible aquí porque nadie lo nota hasta que un runner se pierde.
2. **Que siempre haya respuesta.** Si OSRM no contesta hay que caer al
   haversine: el planeador pierde precisión, no la capacidad de planear.
3. **Que un tramo sin camino no se cuente como cero.** OSRM devuelve `null`
   entre puntos que no conecta; darlo por cero mentiría a la baja.
"""

from __future__ import annotations

import json

import pytest

from lib import ruteo


@pytest.fixture(autouse=True)
def _sin_cache():
    ruteo.olvidar_salud()
    yield
    ruteo.olvidar_salud()


class _Resp:
    def __init__(self, cuerpo, status=200):
        self._cuerpo = json.dumps(cuerpo).encode()
        self.status = status

    def read(self):
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fingir(monkeypatch, cuerpo, capturar=None):
    import urllib.request

    def _urlopen(url, timeout=None):
        u = url if isinstance(url, str) else url.full_url
        if capturar is not None:
            capturar.append(u)
        return _Resp(cuerpo)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)


# ── El orden de las coordenadas ────────────────────────────────────────────


def test_las_coordenadas_viajan_como_las_pide_osrm(monkeypatch):
    """(lat, lng) adentro; (lng, lat) en la URL. Invertirlas no da error: da
    una ruta equivocada, que es mucho peor."""
    urls: list[str] = []
    _fingir(monkeypatch, {"code": "Ok", "routes": [{"distance": 20399.1}]}, urls)

    zocalo = (19.4326, -99.1332)
    satelite = (19.5094, -99.2386)
    ruteo.distancia(zocalo, satelite)

    consulta = [u for u in urls if "/route/" in u][-1]
    assert "-99.1332,19.4326" in consulta, "la longitud debe ir primero"
    assert "19.4326,-99.1332" not in consulta.split("/driving/")[1], (
        "las coordenadas salieron invertidas: eso manda la ruta a otro país"
    )


def test_devuelve_los_metros_de_la_calle(monkeypatch):
    _fingir(monkeypatch, {"code": "Ok", "routes": [{"distance": 20399.1}]})
    d = ruteo.distancia((19.4326, -99.1332), (19.5094, -99.2386))
    assert d == 20399.1
    assert ruteo.ultima_fuente() == ruteo.FUENTE_CALLES


# ── Que nunca se quede sin respuesta ───────────────────────────────────────


def test_sin_osrm_cae_a_la_linea_recta(monkeypatch):
    """El planeador pierde precisión, no la capacidad de planear."""
    import urllib.request

    def _explota(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _explota)
    monkeypatch.setattr(ruteo, "_recta", lambda a, b: 14000.0)

    d = ruteo.distancia((19.4326, -99.1332), (19.5094, -99.2386))
    assert d == 14000.0
    assert ruteo.ultima_fuente() == ruteo.FUENTE_RECTA


def test_una_respuesta_con_error_tambien_cae_a_la_recta(monkeypatch):
    """OSRM contesta 200 con `code != Ok` cuando no puede resolver."""
    _fingir(monkeypatch, {"code": "NoRoute"})
    monkeypatch.setattr(ruteo, "_recta", lambda a, b: 999.0)
    assert ruteo.distancia((1.0, 1.0), (2.0, 2.0)) == 999.0


# ── La matriz, que es lo que justifica el servicio ─────────────────────────


def test_la_matriz_se_pide_en_una_sola_consulta(monkeypatch):
    """Ordenar N paradas pide N×N distancias. Una consulta por par contra un
    servicio público sería imposible; local es una sola llamada."""
    urls: list[str] = []
    _fingir(monkeypatch, {
        "code": "Ok",
        "distances": [[0, 100, 200], [100, 0, 150], [200, 150, 0]],
        "durations": [[0, 10, 20], [10, 0, 15], [20, 15, 0]],
    }, urls)

    m = ruteo.matriz([(19.4, -99.1), (19.5, -99.2), (19.3, -99.0)])
    assert m["fuente"] == ruteo.FUENTE_CALLES
    assert m["distancias"][0][1] == 100
    assert len([u for u in urls if "/table/" in u]) == 1, "se pidió más de una vez"


def test_la_matriz_sin_osrm_se_arma_en_recta(monkeypatch):
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    monkeypatch.setattr(ruteo, "_recta", lambda a, b: 500.0)

    m = ruteo.matriz([(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)])
    assert m["fuente"] == ruteo.FUENTE_RECTA
    assert m["distancias"][0][1] == 500.0
    assert m["distancias"][1][0] == 500.0, "la matriz en recta debe ser simétrica"
    assert m["distancias"][2][2] == 0.0, "la diagonal es cero"


def test_un_solo_punto_no_es_una_matriz():
    assert ruteo.matriz([(1.0, 1.0)]) is None
    assert ruteo.matriz([]) is None


def test_demasiados_puntos_se_recortan(monkeypatch):
    """Una ruta de más de veinticinco paradas no existe en este negocio, y una
    matriz enorme es una forma fácil de hacerse daño solo."""
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    monkeypatch.setattr(ruteo, "_recta", lambda a, b: 1.0)

    m = ruteo.matriz([(float(i), float(i)) for i in range(60)])
    assert len(m["distancias"]) == ruteo.MAX_PUNTOS_MATRIZ


# ── El caso raro que mentiría a la baja ────────────────────────────────────


def test_un_tramo_sin_camino_no_se_cuenta_como_cero(monkeypatch):
    """OSRM devuelve null entre puntos que no conecta (una isla, una
    coordenada en medio del mar). Contarlo como cero diría que el runner no
    recorre nada para llegar."""
    from apps.el_pizarron import ruta as ruta_mod

    monkeypatch.setattr(ruta_mod, "_distancia", lambda a, b: 7777.0)
    monkeypatch.setattr("lib.ruteo.matriz", lambda puntos: {
        "distancias": [[0, None], [None, 0]],
        "duraciones": [],
        "fuente": ruteo.FUENTE_CALLES,
    })

    total = ruta_mod.distancia_total_m([
        {"lat": 19.4, "lng": -99.1},
        {"lat": 19.5, "lng": -99.2},
    ])
    assert total == 7777, "el tramo sin camino se dio por cero"
