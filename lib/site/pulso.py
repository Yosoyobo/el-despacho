"""El pulso de la máquina: la serie corta que dibujan las gráficas de El Vigía.

Un número solo dice cómo está la máquina; una línea dice **hacia dónde va**. Ésa
es toda la diferencia entre «memoria 23%» y «memoria 23%, subiendo desde 18% hace
diez minutos».

**Por qué en Redis y no en memoria del proceso.** Gunicorn corre con varios
workers, cada uno con su propia memoria. Una serie guardada en el proceso saldría
distinta según el worker que atienda el refresco, así que la gráfica daría saltos
cada pocos segundos sin que nada hubiera cambiado. Redis lo ve todo el mundo.

**Por qué la escribe quien la lee.** No hay un cron que muestree: la propia
pantalla, al pedir su panel de fierro cada cinco segundos, deja el punto. Si nadie
mira, no se acumula nada — que es lo correcto: la serie existe para la pared.
Un cron muestreando 24/7 para una pantalla que se ve de día es trabajo tirado.

Nada de aquí lanza nunca. Sin Redis las gráficas salen vacías y los números
grandes siguen ahí; una pared a medias es mejor que una pared caída.
"""

from __future__ import annotations

import logging
import os
import time

import redis

# Cuántos puntos se guardan por serie. A un punto cada 5 s son ~8 minutos de
# historia, que es lo que cabe legible en una gráfica del ancho de un panel.
LARGO = 96
TTL = 3600  # si nadie mira por una hora, la serie se tira: estaría vieja.

logger = logging.getLogger(__name__)
_cliente: redis.Redis | None = None


def _client() -> redis.Redis:
    global _cliente
    if _cliente is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _cliente = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
    return _cliente


def _clave(serie: str) -> str:
    return f"despacho:vigia:pulso:{serie}"


def anotar(serie: str, valor: float | int | None) -> None:
    """Deja un punto. Un valor ausente NO se inventa: se guarda como hueco."""
    try:
        c = _client()
        # El hueco se guarda literal para que la gráfica pueda cortar la línea en
        # vez de fingir continuidad. Un cero ahí mentiría: «la memoria bajó a 0».
        pieza = "" if valor is None else f"{float(valor):.2f}"
        clave = _clave(serie)
        tubo = c.pipeline()
        tubo.lpush(clave, f"{int(time.time())}:{pieza}")
        tubo.ltrim(clave, 0, LARGO - 1)
        tubo.expire(clave, TTL)
        tubo.execute()
    except Exception:  # noqa: BLE001 — el pulso nunca puede tumbar la pantalla
        return


def leer(serie: str) -> list[float | None]:
    """La serie en orden cronológico (lo más viejo primero), lista para dibujar."""
    try:
        crudo = _client().lrange(_clave(serie), 0, LARGO - 1)
    except Exception:  # noqa: BLE001
        return []
    puntos: list[float | None] = []
    for elemento in reversed(crudo or []):
        _, _, pieza = str(elemento).partition(":")
        try:
            puntos.append(float(pieza) if pieza else None)
        except ValueError:
            puntos.append(None)
    return puntos


def anotar_varias(valores: dict[str, float | int | None]) -> None:
    """Varias series de un tiro, en un solo viaje a Redis."""
    try:
        c = _client()
        tubo = c.pipeline()
        ahora = int(time.time())
        for serie, valor in valores.items():
            pieza = "" if valor is None else f"{float(valor):.2f}"
            clave = _clave(serie)
            tubo.lpush(clave, f"{ahora}:{pieza}")
            tubo.ltrim(clave, 0, LARGO - 1)
            tubo.expire(clave, TTL)
        tubo.execute()
    except Exception:  # noqa: BLE001
        return


def leer_varias(series: list[str]) -> dict[str, list[float | None]]:
    """Varias series de un tiro. Devuelve {} si Redis no contesta."""
    try:
        c = _client()
        tubo = c.pipeline()
        for serie in series:
            tubo.lrange(_clave(serie), 0, LARGO - 1)
        crudos = tubo.execute()
    except Exception:  # noqa: BLE001
        return {s: [] for s in series}
    salida: dict[str, list[float | None]] = {}
    for serie, crudo in zip(series, crudos, strict=False):
        puntos: list[float | None] = []
        for elemento in reversed(crudo or []):
            _, _, pieza = str(elemento).partition(":")
            try:
                puntos.append(float(pieza) if pieza else None)
            except ValueError:
                puntos.append(None)
        salida[serie] = puntos
    return salida


def trazo(puntos: list[float | None], *, ancho: int = 100, alto: int = 30,
          maximo: float | None = None) -> str:
    """Los puntos como una `polyline` de SVG, en un sistema de 0..ancho × 0..alto.

    Devuelve cadena vacía si no hay al menos dos puntos: una línea de un punto no
    es una tendencia, y dibujar algo ahí sugeriría una historia que no existe.

    El máximo se puede fijar (para porcentajes, 100) o se toma del propio dato,
    que es lo que hace que una serie de milisegundos se vea con relieve en vez de
    aplastada contra el piso.
    """
    reales = [p for p in puntos if p is not None]
    if len(reales) < 2:
        return ""
    tope = maximo if maximo is not None else max(reales)
    if not tope or tope <= 0:
        tope = 1.0
    n = len(puntos)
    partes: list[str] = []
    for i, p in enumerate(puntos):
        if p is None:
            continue
        x = (i / (n - 1)) * ancho if n > 1 else 0
        y = alto - min(max(p / tope, 0.0), 1.0) * alto
        partes.append(f"{x:.1f},{y:.1f}")
    return " ".join(partes)


def area(puntos: list[float | None], *, ancho: int = 100, alto: int = 30,
         maximo: float | None = None) -> str:
    """Lo mismo pero cerrado contra el piso, para rellenar bajo la línea."""
    linea = trazo(puntos, ancho=ancho, alto=alto, maximo=maximo)
    if not linea:
        return ""
    primero = linea.split(" ")[0].split(",")[0]
    ultimo = linea.split(" ")[-1].split(",")[0]
    return f"{primero},{alto} {linea} {ultimo},{alto}"


__all__ = ["LARGO", "anotar", "anotar_varias", "area", "leer", "leer_varias", "trazo"]
