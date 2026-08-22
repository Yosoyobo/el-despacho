"""Lo que el servidor está atendiendo AHORA, leído de los logs de Docker.

Alimenta la pantalla de El Vigía (`/site/vivo/`): el flujo de peticiones que
atienden El Taller, La Gerencia y El Mostrador, conforme pasan.

**Por qué de los logs y no de un middleware.** Un middleware que fuera anotando
cada petición en Redis o en una tabla sería una escritura extra en el camino
caliente de CADA request, en un sistema de cinco usuarios, para alimentar una
pantalla que casi nadie mira. Los logs ya están escritos —gunicorn y Caddy los
producen de todos modos— y el socket de Docker ya está montado para los gauges.
Leerlos no le cuesta nada a quien está usando el sistema.

**Dos detalles del protocolo que hay que respetar:**

1. El endpoint `/containers/{id}/logs` devuelve un stream **multiplexado** cuando
   el contenedor no tiene TTY (nuestro caso): tramas de 8 bytes de cabecera
   —`[tipo, 0, 0, 0, tamaño de 4 bytes big-endian]`— seguidas de su carga. Si se
   lee como texto plano aparecen bytes de basura pegados al inicio de cada línea.
2. Cada app escribe su propio formato y con su propio reloj (gunicorn en hora
   local con offset, Caddy en UTC). Mezclarlos por su propia marca de tiempo es
   pedir un desorden silencioso, así que se piden los logs con `timestamps=1`:
   Docker prefija CADA línea con la suya, en UTC y ordenable. Ése es el reloj
   común.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from lib.site.contenedores import DOCKER_SOCK, _UnixHTTPConnection, disponible

# Los contenedores que atienden peticiones, con el apodo que se muestra.
SERVICIOS: tuple[tuple[str, str], ...] = (
    ("despacho-el-taller", "Taller"),
    ("despacho-gerencia", "Gerencia"),
    ("despacho-el-mostrador", "Mostrador"),
)

# Rutas que sólo son ruido en una pantalla en vivo: sondas de salud y el sondeo
# que hace la propia página. Sin esto, el flujo se llena de `/ping` cada 10 s y
# tapa lo que de verdad está pasando.
_RUIDO = re.compile(r"^/(ping|salud|sistema/aviso-deploy|site/vivo)")

# gunicorn, formato de acceso por default + la duración que agrega el entrypoint:
#   IP - - [fecha] "MÉTODO /ruta HTTP/1.1" CÓDIGO BYTES "referer" "ua" MICROSEG
_RE_GUNICORN = re.compile(
    r'"(?P<metodo>[A-Z]+)\s+(?P<ruta>\S+)\s+HTTP/[\d.]+"\s+'
    r"(?P<codigo>\d{3})\s+(?P<bytes>\d+|-)"
)
_RE_MICROS = re.compile(r'"\s+(?P<micros>\d+)\s*$')


def _leer_bytes(path: str, *, timeout: float = 3.0) -> bytes:
    conn = _UnixHTTPConnection(DOCKER_SOCK, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        cuerpo = resp.read()
        if resp.status >= 400:
            raise RuntimeError(f"docker API {resp.status}")
        return cuerpo
    finally:
        conn.close()


def _demultiplexar(datos: bytes) -> list[str]:
    """Separa las tramas del stream de Docker y devuelve las líneas de texto.

    Si el contenedor tuviera TTY el stream viene plano; se detecta porque el
    primer byte no es un tipo de trama válido (0, 1 o 2).
    """
    if not datos:
        return []
    if datos[0] not in (0, 1, 2):
        return datos.decode("utf-8", "replace").splitlines()

    lineas: list[str] = []
    i, n = 0, len(datos)
    while i + 8 <= n:
        tamano = int.from_bytes(datos[i + 4:i + 8], "big")
        carga = datos[i + 8:i + 8 + tamano]
        i += 8 + tamano
        lineas.extend(carga.decode("utf-8", "replace").splitlines())
    return lineas


def _marca(linea: str) -> tuple[datetime | None, str]:
    """Separa la marca de tiempo que pone Docker (`timestamps=1`) del resto."""
    cabeza, _, resto = linea.partition(" ")
    try:
        # RFC3339 con nanosegundos; Python aguanta hasta microsegundos.
        cabeza_norm = re.sub(r"\.(\d{6})\d*Z?$", r".\1+00:00", cabeza)
        return datetime.fromisoformat(cabeza_norm.replace("Z", "+00:00")), resto
    except ValueError:
        return None, linea


def _parsear_caddy(resto: str) -> dict[str, Any] | None:
    """El Mostrador escribe `format console`: texto y luego el JSON estructurado."""
    if "handled request" not in resto:
        return None
    inicio = resto.find("{")
    if inicio < 0:
        return None
    try:
        d = json.loads(resto[inicio:])
    except Exception:  # noqa: BLE001 — línea cortada por el buffer
        return None
    pet = d.get("request") or {}
    return {
        "metodo": pet.get("method") or "?",
        "ruta": pet.get("uri") or "?",
        "codigo": d.get("status"),
        "bytes": d.get("size"),
        "ms": round((d.get("duration") or 0) * 1000, 1),
    }


def _parsear_gunicorn(resto: str) -> dict[str, Any] | None:
    m = _RE_GUNICORN.search(resto)
    if not m:
        return None
    micros = _RE_MICROS.search(resto)
    return {
        "metodo": m.group("metodo"),
        "ruta": m.group("ruta"),
        "codigo": int(m.group("codigo")),
        "bytes": None if m.group("bytes") == "-" else int(m.group("bytes")),
        # `%(D)s` es microsegundos. Si el entrypoint todavía no lo agrega, queda
        # en None y la columna sale vacía en vez de mentir con un cero.
        "ms": round(int(micros.group("micros")) / 1000, 1) if micros else None,
    }


def peticiones(limite: int = 40, *, por_servicio: int = 60) -> list[dict[str, Any]]:
    """Las últimas peticiones de los tres servicios, mezcladas y ordenadas.

    Nunca lanza: un contenedor apagado o un socket ausente devuelven lo que se
    pueda leer del resto.
    """
    if not disponible():
        return []

    filas: list[dict[str, Any]] = []
    for contenedor, apodo in SERVICIOS:
        try:
            crudo = _leer_bytes(
                f"/v1.44/containers/{contenedor}/logs"
                f"?stdout=1&stderr=1&timestamps=1&tail={por_servicio}"
            )
        except Exception:  # noqa: BLE001 — contenedor apagado o sin socket
            continue
        for linea in _demultiplexar(crudo):
            cuando, resto = _marca(linea)
            datos = _parsear_caddy(resto) or _parsear_gunicorn(resto)
            if not datos:
                continue
            if _RUIDO.match(datos["ruta"] or ""):
                continue
            filas.append({**datos, "servicio": apodo, "cuando": cuando})

    # Sin marca de tiempo no hay forma de ordenar: van al final, no se descartan.
    filas.sort(key=lambda f: f["cuando"] or datetime.min.replace(tzinfo=UTC),
               reverse=True)
    return filas[:limite]


def resumen(filas: list[dict[str, Any]]) -> dict[str, Any]:
    """Cifras de cabecera del panel: cuántas, cuántas con error, y la más lenta."""
    con_ms = [f["ms"] for f in filas if f.get("ms") is not None]
    errores = [f for f in filas if isinstance(f.get("codigo"), int) and f["codigo"] >= 400]
    return {
        "total": len(filas),
        "errores": len(errores),
        "ms_max": max(con_ms) if con_ms else None,
        "ms_medio": round(sum(con_ms) / len(con_ms), 1) if con_ms else None,
    }


__all__ = ["SERVICIOS", "peticiones", "resumen"]
