"""Lo que el mapa (OSRM) sabe hacer y no se le estaba pidiendo (2026-08-24).

Verificado contra el servidor real antes de escribir el código, no contra la
documentación. Lo que estas pruebas defienden:

1. **Una matriz, no mil consultas.** El planeador preguntaba de un par a la vez
   dentro de sus bucles de optimización: doce paradas entre tres runners eran
   **3,508 consultas**. `Tabla` pide la matriz UNA vez.
2. **Las opciones llegan al mapa.** Evitar casetas cambia la ruta de verdad
   (20356 m → 20111 m, medido); si el parámetro no viaja, no cambia nada y nadie
   se entera.
3. **Las exclusiones NO se combinan** — el servidor contesta «Exclude flag
   combination is not supported», así que el GUI ofrece una a la vez.
4. **El orden de las coordenadas.** El repo habla (lat, lng) y OSRM pide
   (lng, lat). Invertirlas no da error: da una ruta a otro estado.
"""

from __future__ import annotations

import json

import pytest

from lib import ruteo

CENTRO = (19.4326, -99.1332)
SATELITE = (19.5100, -99.2400)


@pytest.fixture(autouse=True)
def _sin_cache():
    ruteo.olvidar_salud()
    ruteo.olvidar_opciones()
    yield
    ruteo.olvidar_salud()
    ruteo.olvidar_opciones()


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


def _fingir(monkeypatch, cuerpo, urls=None):
    import urllib.request

    def _urlopen(url, timeout=None):
        u = url if isinstance(url, str) else url.full_url
        if urls is not None:
            urls.append(u)
        return _Resp(cuerpo)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)


_RUTA_OK = {"code": "Ok", "routes": [{"distance": 20356.4, "duration": 1431.7}]}


# ── 1. Las opciones viajan en la consulta ─────────────────────────────────────

def test_evitar_casetas_llega_al_mapa(monkeypatch):
    urls = []
    _fingir(monkeypatch, _RUTA_OK, urls)
    ruteo.distancia(CENTRO, SATELITE,
                    opciones=ruteo.Opciones(evitar=ruteo.EVITAR_CASETAS))
    assert any("exclude=toll" in u for u in urls), urls


def test_sin_opciones_no_se_manda_exclude(monkeypatch):
    urls = []
    _fingir(monkeypatch, _RUTA_OK, urls)
    ruteo.distancia(CENTRO, SATELITE, opciones=ruteo.OPCIONES_SIMPLES)
    assert not any("exclude" in u for u in urls), urls


def test_la_acera_del_cliente_se_pide_por_destino(monkeypatch):
    """El primer punto es de donde sale; los destinos se abordan por su acera."""
    urls = []
    _fingir(monkeypatch, _RUTA_OK, urls)
    ruteo.distancia(CENTRO, SATELITE,
                    opciones=ruteo.Opciones(acera_del_cliente=True))
    assert any("approaches=unrestricted%3Bcurb" in u or "approaches=unrestricted;curb" in u
               for u in urls), urls


def test_las_coordenadas_viajan_como_las_pide_osrm(monkeypatch):
    """(lat, lng) aquí; (lng, lat) allá. Invertirlas da una ruta a otro estado."""
    urls = []
    _fingir(monkeypatch, _RUTA_OK, urls)
    ruteo.distancia(CENTRO, SATELITE, opciones=ruteo.OPCIONES_SIMPLES)
    assert "-99.1332,19.4326;-99.24,19.51" in urls[-1].replace("%2C", ",")


# ── 2. La matriz ──────────────────────────────────────────────────────────────

_MATRIZ_OK = {
    "code": "Ok",
    "distances": [[0, 1000, 2000], [1000, 0, 1500], [2000, 1500, 0]],
    "durations": [[0, 100, 200], [100, 0, 150], [200, 150, 0]],
}


def test_la_tabla_pide_la_matriz_una_sola_vez(monkeypatch):
    """Es LA razón del servicio: N×N en una consulta en vez de N² consultas."""
    urls = []
    _fingir(monkeypatch, _MATRIZ_OK, urls)
    puntos = [CENTRO, SATELITE, (19.40, -99.16)]
    tabla = ruteo.Tabla(puntos, opciones=ruteo.OPCIONES_SIMPLES)

    for a in puntos:
        for b in puntos:
            tabla.metros(a, b)

    tablas = [u for u in urls if "/table/" in u]
    assert len(tablas) == 1, urls


def test_la_tabla_devuelve_lo_que_dijo_el_mapa(monkeypatch):
    _fingir(monkeypatch, _MATRIZ_OK)
    puntos = [CENTRO, SATELITE, (19.40, -99.16)]
    tabla = ruteo.Tabla(puntos, opciones=ruteo.OPCIONES_SIMPLES)
    assert tabla.metros(puntos[0], puntos[1]) == 1000
    assert tabla.segundos(puntos[0], puntos[1]) == 100
    assert tabla.por_calles


def test_el_factor_de_trafico_multiplica_los_tiempos(monkeypatch):
    """OSRM calcula a calle libre; en esta ciudad eso se queda corto."""
    _fingir(monkeypatch, _MATRIZ_OK)
    tabla = ruteo.Tabla([CENTRO, SATELITE, (19.40, -99.16)],
                        opciones=ruteo.Opciones(factor_trafico=1.5))
    assert tabla.segundos(CENTRO, SATELITE) == pytest.approx(150.0)


def test_el_factor_no_toca_los_metros(monkeypatch):
    _fingir(monkeypatch, _MATRIZ_OK)
    tabla = ruteo.Tabla([CENTRO, SATELITE, (19.40, -99.16)],
                        opciones=ruteo.Opciones(factor_trafico=2.0))
    assert tabla.metros(CENTRO, SATELITE) == 1000


def test_un_punto_desconocido_no_rompe_la_tabla(monkeypatch):
    _fingir(monkeypatch, _MATRIZ_OK)
    tabla = ruteo.Tabla([CENTRO, SATELITE], opciones=ruteo.OPCIONES_SIMPLES)
    # Un punto que no estaba al construirla se mide al vuelo, sin explotar.
    assert isinstance(tabla.metros(CENTRO, (19.9, -99.9)), float)


def test_demasiados_puntos_se_miden_en_recta_completa(monkeypatch):
    """No se RECORTA la lista: una matriz más chica que lo pedido obliga a quien
    llama a adivinar qué falta."""
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    monkeypatch.setattr(ruteo, "_recta", lambda a, b: 1.0)

    n = ruteo.MAX_PUNTOS_MATRIZ + 10
    m = ruteo.matriz([(float(i), float(i)) for i in range(n)],
                     opciones=ruteo.OPCIONES_SIMPLES)
    assert len(m["distancias"]) == n
    assert m["fuente"] == ruteo.FUENTE_RECTA


# ── 3. Dibujar y explicar ─────────────────────────────────────────────────────

def test_el_trazo_devuelve_lat_lng_para_leaflet(monkeypatch):
    """GeoJSON viene en (lng, lat) y Leaflet pinta en (lat, lng)."""
    _fingir(monkeypatch, {
        "code": "Ok",
        "routes": [{"geometry": {"coordinates": [[-99.13, 19.43], [-99.24, 19.51]]}}],
    })
    trazo = ruteo.trazo([CENTRO, SATELITE], opciones=ruteo.OPCIONES_SIMPLES)
    assert trazo == [[19.43, -99.13], [19.51, -99.24]]


def test_el_trazo_pide_la_version_simplificada(monkeypatch):
    """Medido: tres paradas dan 27 puntos simplificado contra 736 completo."""
    urls = []
    _fingir(monkeypatch, {"code": "Ok", "routes": [{"geometry": {"coordinates": []}}]}, urls)
    ruteo.trazo([CENTRO, SATELITE], opciones=ruteo.OPCIONES_SIMPLES)
    assert "overview=simplified" in urls[-1]


def test_las_indicaciones_salen_en_espanol(monkeypatch):
    """OSRM manda `type` + `modifier` en inglés; la frase la armamos aquí."""
    _fingir(monkeypatch, {
        "code": "Ok",
        "routes": [{
            "distance": 1200, "duration": 300,
            "legs": [{"steps": [
                {"name": "Plaza de la Constitución", "distance": 90,
                 "maneuver": {"type": "depart", "modifier": "left"}},
                {"name": "Pino Suárez", "distance": 25,
                 "maneuver": {"type": "turn", "modifier": "right"}},
                {"name": "", "distance": 0,
                 "maneuver": {"type": "arrive", "modifier": "right"}},
            ]}],
        }],
    })
    d = ruteo.indicaciones(CENTRO, SATELITE, opciones=ruteo.OPCIONES_SIMPLES)
    textos = [p["texto"] for p in d["pasos"]]
    assert textos[0].startswith("Arranca")
    assert textos[1] == "Da vuelta a la derecha a Pino Suárez"
    assert "Llegaste" in textos[2]


def test_las_indicaciones_llevan_el_factor_de_trafico(monkeypatch):
    _fingir(monkeypatch, {
        "code": "Ok",
        "routes": [{"distance": 1000, "duration": 600, "legs": [{"steps": []}]}],
    })
    d = ruteo.indicaciones(CENTRO, SATELITE,
                           opciones=ruteo.Opciones(factor_trafico=1.5))
    assert d["segundos"] == 900


def test_cerca_de_calle_dice_a_cuanto_quedo_el_pin(monkeypatch):
    _fingir(monkeypatch, {
        "code": "Ok",
        "waypoints": [{"distance": 67.4, "name": "Plaza de la Constitución"}],
    })
    r = ruteo.cerca_de_calle(19.4326, -99.1332, opciones=ruteo.OPCIONES_SIMPLES)
    assert r["metros"] == pytest.approx(67.4)
    assert r["calle"] == "Plaza de la Constitución"


# ── 4. Siempre hay respuesta ──────────────────────────────────────────────────

def test_sin_mapa_todo_cae_a_la_linea_recta(monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    monkeypatch.setattr(ruteo, "_recta", lambda a, b: 4242.0)

    assert ruteo.distancia(CENTRO, SATELITE, opciones=ruteo.OPCIONES_SIMPLES) == 4242.0
    assert ruteo.ultima_fuente() == ruteo.FUENTE_RECTA
    tabla = ruteo.Tabla([CENTRO, SATELITE], opciones=ruteo.OPCIONES_SIMPLES)
    assert not tabla.por_calles
    assert tabla.metros(CENTRO, SATELITE) == 4242.0
    assert tabla.segundos(CENTRO, SATELITE) is None
    assert ruteo.trazo([CENTRO, SATELITE], opciones=ruteo.OPCIONES_SIMPLES) is None
    assert ruteo.indicaciones(CENTRO, SATELITE, opciones=ruteo.OPCIONES_SIMPLES) is None
    assert ruteo.cerca_de_calle(19.4, -99.1, opciones=ruteo.OPCIONES_SIMPLES) is None


def test_un_tramo_sin_camino_se_mide_en_recta_no_en_cero(monkeypatch):
    """OSRM devuelve null entre puntos que no conecta. Cero mentiría a la baja."""
    _fingir(monkeypatch, {
        "code": "Ok",
        "distances": [[0, None], [None, 0]],
        "durations": [[0, None], [None, 0]],
    })
    monkeypatch.setattr(ruteo, "_recta", lambda a, b: 7777.0)
    tabla = ruteo.Tabla([CENTRO, SATELITE], opciones=ruteo.OPCIONES_SIMPLES)
    assert tabla.metros(CENTRO, SATELITE) == 7777.0


# ── 5. El modo de transporte NO es opción de tiempo de ejecución ──────────────

def test_sin_mapa_de_bici_se_mide_con_el_de_coche(monkeypatch):
    """Verificado contra el servidor: `car`, `bike` y `foot` en la URL devuelven
    lo mismo — el perfil se hornea con el mapa. Sin un segundo servidor, ofrecer
    bicicleta sería prometer algo que no pasa."""
    monkeypatch.setattr(ruteo, "BASE_URL_BICI", "")
    assert ruteo._base(ruteo.Opciones(modo=ruteo.MODO_BICI)) == ruteo.BASE_URL


def test_con_mapa_de_bici_se_pregunta_al_otro_servidor(monkeypatch):
    monkeypatch.setattr(ruteo, "BASE_URL_BICI", "http://osrm-bici:5000")
    assert ruteo._base(ruteo.Opciones(modo=ruteo.MODO_BICI)) == "http://osrm-bici:5000"
    assert ruteo._base(ruteo.Opciones(modo=ruteo.MODO_COCHE)) == ruteo.BASE_URL


# ── El segundo mapa: que quede cableado y no se pierda en silencio ────────────
#
# El modo de falla que cuidan estas tres es el MISMO y es callado: si el
# cableado se rompe, elegir «bicicleta» sigue midiendo en coche sin que nada lo
# diga — números plausibles y equivocados, que es lo peor que puede pasar aquí.


def _raiz():
    import pathlib
    return pathlib.Path(__file__).resolve().parent.parent


def test_el_mapa_de_bici_es_un_servidor_aparte_con_su_propia_carpeta():
    """El perfil se hornea al cocinar el mapa: pedirle «bike» al servidor de
    coche devuelve una ruta de coche sin avisar. Por eso son dos servidores, y
    por eso el de bici NO puede compartir la carpeta del otro."""
    compose = (_raiz() / "docker-compose.servicios.yml").read_text(encoding="utf-8")
    assert "osrm-bici:" in compose
    assert './data/osrm-bici:/data:ro' in compose
    # Detrás de su propio perfil: sin mapa cocido no arranca, y un contenedor
    # reiniciándose en bucle enciende el banner rojo con razón.
    bloque = compose.split("osrm-bici:", 1)[1].split("\n  # ──", 1)[0]
    assert 'profiles: ["osrm-bici"]' in bloque


def test_las_apps_reciben_la_direccion_del_mapa_de_bici():
    """Vacía mientras no exista el mapa: así `lib.ruteo` sabe que no hay bici.
    Si alguien borra la variable del overlay, el modo bici mediría en coche."""
    overlay = (_raiz() / "docker-compose.nuc.yml").read_text(encoding="utf-8")
    # Se cuentan RENGLONES que la declaran, no apariciones: cada uno la nombra
    # dos veces (`OSRM_URL_BICI: "${OSRM_URL_BICI:-}"`).
    declaran = [ln for ln in overlay.splitlines()
                if ln.strip().startswith("OSRM_URL_BICI:")]
    assert len(declaran) == 2, "la piden El Taller y La Gerencia"


def test_el_despliegue_prende_la_bici_solo_con_su_mapa():
    """Y la apaga explícitamente cuando no está: dejar la variable con un valor
    viejo apuntaría a un servidor que no existe."""
    guion = (_raiz() / "infra/scripts/deploy_nuc.sh").read_text(encoding="utf-8")
    assert "data/osrm-bici/mexico-latest.osrm.properties" in guion
    assert 'export OSRM_URL_BICI="http://osrm-bici:5000"' in guion
    assert 'export OSRM_URL_BICI=""' in guion


def test_hay_guion_para_cocinar_el_mapa():
    """El mapa de coche se preparó a mano y no quedó escrito: si el disco muere,
    nadie sabe rehacerlo. Este guion es esa receta, y sirve para los dos."""
    guion = _raiz() / "infra/scripts/cocinar_mapa.sh"
    assert guion.exists()
    import os
    assert os.access(guion, os.X_OK), "tiene que poder ejecutarse"
    texto = guion.read_text(encoding="utf-8")
    assert "osrm-extract" in texto and "osrm-partition" in texto and "osrm-customize" in texto
    assert "bicycle" in texto
