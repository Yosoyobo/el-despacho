"""Distancias, trazos e indicaciones por calles reales, con OSRM en el NUC.

Hasta 2026-08-24 el planeador medía en **línea recta** (el haversine de El
Checador). El orden de las paradas salía bien la mayoría de las veces, pero los
kilómetros y las horas eran estimados — y de esas horas salen las que el runner
ve en su ruta. Medido entre el Zócalo y Ciudad Satélite: 14.0 km en línea recta
contra **20.4 km por calle**, un 46 % de diferencia.

**La matriz es lo que justifica el servicio.** Ordenar N paradas no pide una
distancia sino N×N: contra un servicio público sería imposible por el límite de
peticiones, y contra uno local es una sola llamada que responde al instante.
`Tabla` es la forma de aprovecharla — se pide UNA vez y luego se consulta como
un diccionario. Sin ella, el planeador hacía **3,508 consultas** para repartir
doce paradas entre tres runners (medido el 2026-08-24); con ella, una.

**Siempre hay respuesta.** Si OSRM no contesta se cae al haversine de siempre,
así que el planeador nunca se queda sin poder planear: pierde precisión, no
funcionalidad. Quien llama puede saber cuál se usó con `ultima_fuente()`.

Lo que se puede pedir en caliente y lo que no
---------------------------------------------
Verificado contra nuestro servidor, no contra la documentación:

- **Sí**: evitar casetas o autopistas, llegar por la acera del cliente, trazo
  por calles, indicaciones giro a giro, pegar un punto a la calle más cercana.
- **No**: combinar dos exclusiones (`exclude=toll,motorway` → *«Exclude flag
  combination is not supported»*: el perfil sólo trae precocidas las sueltas),
  y el **modo de transporte**, que se hornea con el mapa — `car`, `bike` y
  `foot` en la URL devuelven hoy exactamente lo mismo porque sólo se coció el
  perfil de coche. Para bici hay un segundo servidor con su propio mapa.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
from dataclasses import dataclass

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get("OSRM_URL", "http://osrm:5000")
#: Segundo servidor, con el mapa cocido con el perfil de bicicleta. Vacío = no
#: hay, y el modo bici cae al de coche en vez de dejar de funcionar.
BASE_URL_BICI = os.environ.get("OSRM_URL_BICI", "")

TIMEOUT_SALUD = 1.5
TIMEOUT_CONSULTA = 8.0
#: La matriz grande tarda más que una ruta: 60×60 son 485 ms medidos.
TIMEOUT_MATRIZ = 20.0

#: Cuánto dura el veredicto de `disponible()`. Sin esto se sondearía en cada
#: planeación; con esto, una vez por minuto.
TTL_SALUD = 60.0

#: Tope de puntos por matriz. OSRM se arrancó con `--max-table-size 2000`; el
#: tope de aquí es prudencia, no del servidor. Subió de 25 a 100 cuando la
#: matriz pasó a cubrir el día ENTERO (los orígenes de todos los runners más
#: todas las paradas), que es bastante más que una ruta. Medido: 60 puntos en
#: 485 ms, 25 en 178 ms.
MAX_PUNTOS_MATRIZ = 100

FUENTE_CALLES = "calles"
FUENTE_RECTA = "recta"

MODO_COCHE = "coche"
MODO_BICI = "bici"

#: Las exclusiones que el perfil trae precocidas. Van de UNA en UNA.
EVITAR_NADA = ""
EVITAR_CASETAS = "toll"
EVITAR_AUTOPISTA = "motorway"
EVITAR_TRANSBORDADOR = "ferry"
EVITABLES = (EVITAR_NADA, EVITAR_CASETAS, EVITAR_AUTOPISTA, EVITAR_TRANSBORDADOR)

_salud: dict[str, tuple[float, bool]] = {}
_ultima_fuente = FUENTE_RECTA


@dataclass(frozen=True)
class Opciones:
    """Cómo se quiere medir. Sale de La Gerencia → Ajustes → Rutas.

    `evitar` es UNA sola (ver el encabezado del módulo). `factor_trafico`
    multiplica las duraciones: OSRM las calcula a flujo libre, sin tráfico, y
    en esta ciudad eso se queda corto.
    """

    evitar: str = EVITAR_NADA
    acera_del_cliente: bool = False
    factor_trafico: float = 1.0
    modo: str = MODO_COCHE

    def con(self, **cambios) -> Opciones:
        from dataclasses import replace
        return replace(self, **cambios)


OPCIONES_SIMPLES = Opciones()

#: Los ajustes vigentes, recordados un ratito: medir un día son decenas de
#: llamadas y no tiene caso preguntarle a la base en cada una.
_TTL_OPCIONES = 60.0
_cache_opciones: dict = {"hasta": None, "valor": None}


def opciones_vigentes() -> Opciones:
    """Lo configurado en La Gerencia, o los valores neutros si no se puede leer.

    Defensivo a propósito: sin la tabla migrada o con la base muda, se mide como
    siempre en vez de dejar de medir.
    """
    ahora = time.monotonic()
    if _cache_opciones["valor"] is not None and _cache_opciones["hasta"] and ahora < _cache_opciones["hasta"]:
        return _cache_opciones["valor"]

    valor = OPCIONES_SIMPLES
    try:
        from ajustes.models import ConfiguracionRutas

        cfg = ConfiguracionRutas.obtener()
        evitar = (cfg.evitar or EVITAR_NADA).strip()
        factor = float(cfg.factor_trafico or 1)
        valor = Opciones(
            evitar=evitar if evitar in EVITABLES else EVITAR_NADA,
            acera_del_cliente=bool(cfg.acera_del_cliente),
            # Un factor menor a 1 diría que se llega antes de lo que OSRM cree,
            # que es justo al revés de lo que pasa en la calle.
            factor_trafico=factor if factor >= 1.0 else 1.0,
            modo=cfg.modo if cfg.modo in (MODO_COCHE, MODO_BICI) else MODO_COCHE,
        )
    except Exception:  # noqa: BLE001 — sin configuración se mide con lo neutro
        logger.debug("ruteo: no se pudo leer la configuración", exc_info=True)

    _cache_opciones.update(hasta=ahora + _TTL_OPCIONES, valor=valor)
    return valor


def olvidar_opciones() -> None:
    """Tira el recuerdo de la configuración. La llama el GUI al guardar."""
    _cache_opciones.update(hasta=None, valor=None)


# ── Armar la consulta ─────────────────────────────────────────────────────────

def _base(opciones: Opciones) -> str:
    """A qué servidor preguntarle. Sin mapa de bici, se usa el de coche: medir
    de más es mejor que no medir."""
    if opciones.modo == MODO_BICI and BASE_URL_BICI:
        return BASE_URL_BICI
    return BASE_URL


def _coords(puntos) -> str:
    """(lat, lng) → «lng,lat;lng,lat». OSRM las pide al revés que todo el repo:
    invertirlas manda a Texas una ruta de la Ciudad de México, y no da error."""
    return ";".join(f"{lng},{lat}" for lat, lng in puntos)


def _url(servicio: str, puntos, opciones: Opciones, **params) -> str:
    if opciones.evitar:
        params["exclude"] = opciones.evitar
    if opciones.acera_del_cliente and len(puntos) > 1:
        # El primer punto es de donde sale; los destinos se abordan por su
        # acera para que el runner no cruce la avenida con la caja.
        params["approaches"] = ";".join(
            ["unrestricted"] + ["curb"] * (len(puntos) - 1))
    query = urllib.parse.urlencode(params, safe=",;")
    return f"{_base(opciones)}/{servicio}/v1/driving/{_coords(puntos)}?{query}"


def _pedir(url: str, *, timeout: float = TIMEOUT_CONSULTA) -> dict | None:
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=timeout) as r:
            if r.status != 200:
                return None
            datos = json.loads(r.read())
        return datos if datos.get("code") == "Ok" else None
    except Exception as exc:  # noqa: BLE001 — se cae a la línea recta
        logger.warning("ruteo: consulta fallida: %s", exc)
        return None


# ── ¿Está en pie? ─────────────────────────────────────────────────────────────

def ultima_fuente() -> str:
    """`calles` o `recta`: con qué se midió lo último que se preguntó."""
    return _ultima_fuente


def disponible(*, forzar: bool = False, opciones: Opciones | None = None) -> bool:
    opciones = opciones or opciones_vigentes()
    base = _base(opciones)
    ahora = time.monotonic()
    guardado = _salud.get(base)
    if not forzar and guardado is not None and ahora - guardado[0] < TTL_SALUD:
        return guardado[1]
    veredicto = _sondear(base)
    _salud[base] = (ahora, veredicto)
    return veredicto


def _sondear(base: str) -> bool:
    try:
        import urllib.request

        # El servicio no expone /health, así que se le pide una ruta de un punto
        # a sí mismo: es la consulta más barata que confirma que contesta.
        url = (f"{base}/route/v1/driving/"
               "-99.1332,19.4326;-99.1332,19.4326?overview=false")
        with urllib.request.urlopen(url, timeout=TIMEOUT_SALUD) as r:
            return r.status == 200
    except Exception as exc:  # noqa: BLE001 — no responder es la respuesta
        logger.info("ruteo: OSRM no disponible (%s): %s", base, exc)
        return False


def _recta(a: tuple[float, float], b: tuple[float, float]) -> float | None:
    """El haversine de El Checador — la medida de siempre."""
    try:
        from apps.checador.models.sede import distancia_m

        return distancia_m(a[0], a[1], b[0], b[1])
    except Exception as exc:  # noqa: BLE001
        logger.debug("ruteo: no se pudo medir en recta: %s", exc)
        return None


# ── Medir ─────────────────────────────────────────────────────────────────────

def distancia(a: tuple[float, float], b: tuple[float, float],
              *, opciones: Opciones | None = None) -> float | None:
    """Metros entre dos puntos, por calle si se puede."""
    global _ultima_fuente
    opciones = opciones or opciones_vigentes()
    if disponible(opciones=opciones):
        datos = _pedir(_url("route", [a, b], opciones, overview="false"))
        if datos and datos.get("routes"):
            _ultima_fuente = FUENTE_CALLES
            return float(datos["routes"][0]["distance"])
    _ultima_fuente = FUENTE_RECTA
    return _recta(a, b)


def matriz(puntos: list[tuple[float, float]],
           *, opciones: Opciones | None = None) -> dict | None:
    """Distancias y tiempos entre TODOS los puntos, en una sola consulta.

    Devuelve `{"distancias": [[m]], "duraciones": [[s]], "fuente": …}` o None si
    no hay con qué. Las duraciones vienen ya multiplicadas por el factor de
    tráfico: OSRM las calcula a flujo libre.
    """
    global _ultima_fuente
    opciones = opciones or opciones_vigentes()
    if len(puntos) < 2:
        return None
    if len(puntos) > MAX_PUNTOS_MATRIZ:
        # No se recorta la lista: devolver una matriz más chica que los puntos
        # pedidos obliga a quien llama a adivinar qué falta. Se mide todo en
        # recta, que es exacto en su forma aunque menos preciso.
        logger.warning("ruteo: %d puntos exceden el tope de %d; se mide en recta",
                       len(puntos), MAX_PUNTOS_MATRIZ)
        return _matriz_recta(puntos)

    if disponible(opciones=opciones):
        url = _url("table", puntos, opciones, annotations="distance,duration")
        datos = _pedir(url, timeout=TIMEOUT_MATRIZ)
        if datos and datos.get("distances"):
            _ultima_fuente = FUENTE_CALLES
            return {
                "distancias": datos["distances"],
                "duraciones": _con_trafico(datos.get("durations") or [],
                                           opciones.factor_trafico),
                "fuente": FUENTE_CALLES,
            }

    return _matriz_recta(puntos)


def _con_trafico(duraciones, factor: float):
    """Multiplica los segundos por el factor de tráfico, respetando los nulos."""
    if not duraciones or factor == 1.0:
        return duraciones
    return [[None if v is None else v * factor for v in fila] for fila in duraciones]


def _matriz_recta(puntos) -> dict:
    """Sin OSRM: N² cuentas, que para veinte paradas son cuatrocientas — nada."""
    global _ultima_fuente
    _ultima_fuente = FUENTE_RECTA
    n = len(puntos)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = _recta(puntos[i], puntos[j]) or 0.0
            dist[i][j] = dist[j][i] = d
    return {"distancias": dist, "duraciones": [], "fuente": FUENTE_RECTA}


class Tabla:
    """Las distancias entre un conjunto de puntos, pedidas UNA vez.

    Es lo que convierte el planeador de miles de consultas a una. Se construye
    con todos los puntos del día (los orígenes de cada runner y todas las
    paradas) y luego se consulta como un diccionario.

    Un punto que no estaba al construirla no rompe nada: se mide al vuelo.
    """

    def __init__(self, puntos, *, opciones: Opciones | None = None):
        self.opciones = opciones or opciones_vigentes()
        self._indice: dict[tuple, int] = {}
        unicos: list[tuple[float, float]] = []
        for p in puntos:
            if p is None:
                continue
            clave = self._clave(p)
            if clave not in self._indice:
                self._indice[clave] = len(unicos)
                unicos.append(p)
        self._puntos = unicos
        datos = matriz(unicos, opciones=self.opciones) if len(unicos) >= 2 else None
        self._dist = (datos or {}).get("distancias") or []
        self._dur = (datos or {}).get("duraciones") or []
        self.fuente = (datos or {}).get("fuente", FUENTE_RECTA)

    @staticmethod
    def _clave(p) -> tuple:
        return (round(float(p[0]), 6), round(float(p[1]), 6))

    def _par(self, a, b):
        if not a or not b:
            return None
        i = self._indice.get(self._clave(a))
        j = self._indice.get(self._clave(b))
        return None if i is None or j is None else (i, j)

    def metros(self, a, b) -> float:
        """Metros entre dos puntos. 0 si alguno no se puede ubicar."""
        par = self._par(a, b)
        if par is None:
            return distancia(a, b, opciones=self.opciones) or 0.0 if a and b else 0.0
        i, j = par
        try:
            valor = self._dist[i][j]
        except IndexError:
            valor = None
        if valor is None:
            # OSRM devuelve null entre puntos que no conecta (una isla, una
            # coordenada en medio del mar). Darlo por cero mentiría a la baja.
            return _recta(a, b) or 0.0
        return float(valor)

    def segundos(self, a, b) -> float | None:
        """Segundos de viaje si OSRM los dio; None para que quien llame decida."""
        par = self._par(a, b)
        if par is None or not self._dur:
            return None
        i, j = par
        try:
            valor = self._dur[i][j]
        except IndexError:
            return None
        return None if valor is None else float(valor)

    @property
    def por_calles(self) -> bool:
        return self.fuente == FUENTE_CALLES


# ── Dibujar y explicar ────────────────────────────────────────────────────────

def trazo(puntos, *, opciones: Opciones | None = None) -> list[list[float]] | None:
    """El recorrido por calles como lista de [lat, lng], para pintarlo en el mapa.

    `overview=simplified` y no `full` a propósito: medido, tres paradas dan 27
    puntos simplificado contra 736 completo, y a la escala de un mapa de ciudad
    se ven igual.
    """
    opciones = opciones or opciones_vigentes()
    if len(puntos) < 2 or not disponible(opciones=opciones):
        return None
    datos = _pedir(_url("route", puntos, opciones,
                        geometries="geojson", overview="simplified"))
    if not datos or not datos.get("routes"):
        return None
    coords = datos["routes"][0].get("geometry", {}).get("coordinates") or []
    # GeoJSON viene en (lng, lat) y Leaflet pinta en (lat, lng).
    return [[lat, lng] for lng, lat in coords]


#: Cómo se dice cada maniobra. OSRM las devuelve en inglés y sin frase armada:
#: manda `type` + `modifier` y el nombre de la calle. Esto es el equivalente
#: mínimo de `osrm-text-instructions`, que es una librería de JavaScript.
_GIROS = {
    "sharp right": "cerrada a la derecha",
    "right": "a la derecha",
    "slight right": "ligeramente a la derecha",
    "straight": "de frente",
    "slight left": "ligeramente a la izquierda",
    "left": "a la izquierda",
    "sharp left": "cerrada a la izquierda",
    "uturn": "en U",
}


def _frase(paso: dict, es_ultimo: bool) -> str:
    m = paso.get("maneuver") or {}
    tipo = m.get("type") or ""
    giro = _GIROS.get(m.get("modifier") or "", "")
    calle = (paso.get("name") or "").strip()
    en = f" por {calle}" if calle else ""
    a = f" a {calle}" if calle else ""

    if tipo == "depart":
        return f"Arranca{en}".strip()
    if tipo == "arrive":
        lado = _GIROS.get(m.get("modifier") or "", "")
        if lado in ("a la derecha", "a la izquierda"):
            return f"Llegaste — queda {lado}"
        return "Llegaste"
    if tipo == "turn":
        return f"Da vuelta {giro}{a}".strip()
    if tipo == "new name":
        return f"Sigue{en}".strip()
    if tipo == "continue":
        return f"Continúa {giro}{en}".strip()
    if tipo == "merge":
        return f"Incorpórate {giro}{a}".strip()
    if tipo == "on ramp":
        return f"Toma la entrada {giro}{a}".strip()
    if tipo == "off ramp":
        return f"Toma la salida {giro}{a}".strip()
    if tipo == "fork":
        return f"En la bifurcación, {giro}{a}".strip()
    if tipo == "end of road":
        return f"Al final de la calle, {giro}{a}".strip()
    if tipo in ("roundabout", "rotary"):
        salida = m.get("exit")
        cual = f" y toma la salida {salida}" if salida else ""
        return f"Entra a la glorieta{cual}{a}".strip()
    if tipo in ("exit roundabout", "exit rotary"):
        return f"Sal de la glorieta{a}".strip()
    if tipo == "roundabout turn":
        return f"En la glorieta, {giro}{a}".strip()
    # `notification` y cualquier tipo que OSRM agregue después.
    return (f"Sigue {giro}{en}".strip() if giro or calle
            else ("Llegaste" if es_ultimo else "Continúa"))


def indicaciones(a: tuple[float, float], b: tuple[float, float],
                 *, opciones: Opciones | None = None) -> dict | None:
    """Cómo llegar de un punto a otro, giro por giro y en español.

    Devuelve `{"metros", "segundos", "pasos": [{"texto", "metros", "calle"}]}`
    o None si no se puede — quien llama enseña entonces el botón del mapa de
    siempre, que es lo que había antes de esto.
    """
    opciones = opciones or opciones_vigentes()
    if not disponible(opciones=opciones):
        return None
    datos = _pedir(_url("route", [a, b], opciones, steps="true", overview="false"))
    if not datos or not datos.get("routes"):
        return None
    ruta = datos["routes"][0]
    pasos_osrm = []
    for tramo in ruta.get("legs") or []:
        pasos_osrm.extend(tramo.get("steps") or [])
    pasos = [
        {
            "texto": _frase(p, i == len(pasos_osrm) - 1),
            "metros": int(p.get("distance") or 0),
            "calle": (p.get("name") or "").strip(),
        }
        for i, p in enumerate(pasos_osrm)
    ]
    return {
        "metros": int(ruta.get("distance") or 0),
        "segundos": int((ruta.get("duration") or 0) * opciones.factor_trafico),
        "pasos": pasos,
    }


def cerca_de_calle(lat: float, lng: float,
                   *, opciones: Opciones | None = None) -> dict | None:
    """A qué distancia quedó el punto de la calle más cercana, y cuál es.

    Sirve para avisar que un pin cayó en medio de una manzana. **Avisa, no
    bloquea**: la ubicación nunca detiene una acción en este repo.
    """
    opciones = opciones or opciones_vigentes()
    if not disponible(opciones=opciones):
        return None
    datos = _pedir(_url("nearest", [(lat, lng)], opciones, number="1"))
    if not datos or not datos.get("waypoints"):
        return None
    w = datos["waypoints"][0]
    return {"metros": float(w.get("distance") or 0), "calle": (w.get("name") or "").strip()}


def olvidar_salud() -> None:
    """Tira el caché del sondeo. Para pruebas y tras un despliegue."""
    _salud.clear()


__all__ = [
    "BASE_URL",
    "BASE_URL_BICI",
    "EVITABLES",
    "EVITAR_AUTOPISTA",
    "EVITAR_CASETAS",
    "EVITAR_NADA",
    "EVITAR_TRANSBORDADOR",
    "FUENTE_CALLES",
    "FUENTE_RECTA",
    "MAX_PUNTOS_MATRIZ",
    "MODO_BICI",
    "MODO_COCHE",
    "Opciones",
    "Tabla",
    "cerca_de_calle",
    "disponible",
    "distancia",
    "indicaciones",
    "matriz",
    "olvidar_opciones",
    "olvidar_salud",
    "opciones_vigentes",
    "trazo",
    "ultima_fuente",
]
