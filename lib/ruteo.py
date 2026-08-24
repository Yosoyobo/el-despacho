"""Distancias por calles reales, con OSRM corriendo en el NUC.

Hasta hoy el planeador medía en **línea recta** (el haversine de El Checador).
El orden de las paradas salía bien la mayoría de las veces, pero los
kilómetros y las horas eran estimados — y de esas horas salen las que el
runner ve en su ruta. Medido el 2026-08-24 entre el Zócalo y Ciudad Satélite:
14.0 km en línea recta contra **20.4 km por calle**, un 46 % de diferencia. Un
río, un eje sin retorno o una barranca le mienten al orden, no sólo al total.

**La matriz es lo que justifica el servicio.** Ordenar N paradas no pide una
distancia sino N×N: contra un servicio público sería imposible por el límite
de peticiones, y contra uno local es una sola llamada que responde al
instante.

**Siempre hay respuesta.** Si OSRM no contesta se cae al haversine de siempre,
así que el planeador nunca se queda sin poder planear: pierde precisión, no
funcionalidad. Quien llama puede saber cuál se usó con `ultima_fuente()`.
"""

from __future__ import annotations

import json
import logging
import os
import time

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get("OSRM_URL", "http://osrm:5000")

TIMEOUT_SALUD = 1.5
TIMEOUT_CONSULTA = 8.0

#: Cuánto dura el veredicto de `disponible()`. Sin esto se sondearía en cada
#: planeación; con esto, una vez por minuto.
TTL_SALUD = 60.0

#: Tope de puntos por matriz. OSRM se arrancó con `--max-table-size 2000`, pero
#: una ruta de más de 25 paradas no existe en este negocio y una matriz enorme
#: es una forma fácil de hacerse daño solo.
MAX_PUNTOS_MATRIZ = 25

FUENTE_CALLES = "calles"
FUENTE_RECTA = "recta"

_salud: tuple[float, bool] | None = None
_ultima_fuente = FUENTE_RECTA


def ultima_fuente() -> str:
    """`calles` o `recta`: con qué se midió lo último que se preguntó."""
    return _ultima_fuente


def disponible(*, forzar: bool = False) -> bool:
    global _salud
    ahora = time.monotonic()
    if not forzar and _salud is not None and ahora - _salud[0] < TTL_SALUD:
        return _salud[1]
    veredicto = _sondear()
    _salud = (ahora, veredicto)
    return veredicto


def _sondear() -> bool:
    try:
        import urllib.request

        # Una consulta trivial: el servicio no expone /health, así que se le
        # pide una ruta de un punto a sí mismo.
        url = f"{BASE_URL}/route/v1/driving/-99.1332,19.4326;-99.1332,19.4326?overview=false"
        with urllib.request.urlopen(url, timeout=TIMEOUT_SALUD) as r:
            return r.status == 200
    except Exception as exc:  # noqa: BLE001 — no responder es la respuesta
        logger.info("ruteo: OSRM no disponible (%s): %s", BASE_URL, exc)
        return False


def _recta(a: tuple[float, float], b: tuple[float, float]) -> float | None:
    """El haversine de El Checador — la medida de siempre."""
    try:
        from apps.checador.models.sede import distancia_m

        return distancia_m(a[0], a[1], b[0], b[1])
    except Exception as exc:  # noqa: BLE001
        logger.debug("ruteo: no se pudo medir en recta: %s", exc)
        return None


def _pedir(url: str) -> dict | None:
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=TIMEOUT_CONSULTA) as r:
            if r.status != 200:
                return None
            datos = json.loads(r.read())
        return datos if datos.get("code") == "Ok" else None
    except Exception as exc:  # noqa: BLE001 — se cae a la línea recta
        logger.warning("ruteo: consulta fallida: %s", exc)
        return None


def distancia(a: tuple[float, float], b: tuple[float, float]) -> float | None:
    """Metros entre dos puntos, por calle si se puede.

    Ojo con el orden de las coordenadas: aquí se reciben (lat, lng) porque es
    lo que usa todo el repo, y OSRM las pide al revés. Invertirlas manda a
    Texas una ruta de la Ciudad de México, y no da error: da una ruta.
    """
    global _ultima_fuente
    if disponible():
        url = f"{BASE_URL}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}?overview=false"
        datos = _pedir(url)
        if datos and datos.get("routes"):
            _ultima_fuente = FUENTE_CALLES
            return float(datos["routes"][0]["distance"])
    _ultima_fuente = FUENTE_RECTA
    return _recta(a, b)


def matriz(puntos: list[tuple[float, float]]) -> dict | None:
    """Distancias y tiempos entre TODOS los puntos, en una sola consulta.

    Devuelve `{"distancias": [[m]], "duraciones": [[s]], "fuente": …}` o None
    si no hay con qué. Es lo que le permite al planeador ordenar sin hacer una
    consulta por cada par.
    """
    global _ultima_fuente
    if len(puntos) < 2:
        return None
    if len(puntos) > MAX_PUNTOS_MATRIZ:
        logger.warning("ruteo: %d puntos exceden el tope de %d; se recorta",
                       len(puntos), MAX_PUNTOS_MATRIZ)
        puntos = puntos[:MAX_PUNTOS_MATRIZ]

    if disponible():
        coords = ";".join(f"{lng},{lat}" for lat, lng in puntos)
        url = f"{BASE_URL}/table/v1/driving/{coords}?annotations=distance,duration"
        datos = _pedir(url)
        if datos and datos.get("distances"):
            _ultima_fuente = FUENTE_CALLES
            return {
                "distancias": datos["distances"],
                "duraciones": datos.get("durations") or [],
                "fuente": FUENTE_CALLES,
            }

    # Sin OSRM: la matriz se arma con el haversine. Cuesta N² cuentas, que para
    # veinte paradas son cuatrocientas — nada.
    _ultima_fuente = FUENTE_RECTA
    n = len(puntos)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = _recta(puntos[i], puntos[j]) or 0.0
            dist[i][j] = dist[j][i] = d
    return {"distancias": dist, "duraciones": [], "fuente": FUENTE_RECTA}


def olvidar_salud() -> None:
    """Tira el caché del sondeo. Para pruebas y tras un despliegue."""
    global _salud
    _salud = None


__all__ = [
    "BASE_URL",
    "FUENTE_CALLES",
    "FUENTE_RECTA",
    "MAX_PUNTOS_MATRIZ",
    "disponible",
    "distancia",
    "matriz",
    "olvidar_salud",
    "ultima_fuente",
]
