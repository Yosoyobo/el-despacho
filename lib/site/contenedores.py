"""Cliente mínimo sobre el socket de Docker (UNIX). Lee containers, su estado
y stats básicos. No depende de la SDK de docker (`pip install docker`) ni del
CLI — solo stdlib.
"""

from __future__ import annotations

import http.client
import json
import os
import socket
from typing import Any

DOCKER_SOCK = os.environ.get("SITE_DOCKER_SOCK", "/var/run/docker.sock")


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, sock_path: str, timeout: float = 3.0):
        super().__init__("localhost", timeout=timeout)
        self._sock_path = sock_path

    def connect(self) -> None:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self._sock_path)
        self.sock = s


def _get(path: str, *, sock: str | None = None, timeout: float = 3.0) -> Any:
    conn = _UnixHTTPConnection(sock or DOCKER_SOCK, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        if resp.status >= 400:
            raise RuntimeError(f"docker API {resp.status}: {body[:200]!r}")
        return json.loads(body) if body else None
    finally:
        conn.close()


def disponible() -> bool:
    return os.path.exists(DOCKER_SOCK)


def info() -> dict[str, Any]:
    if not disponible():
        return {"disponible": False}
    try:
        d = _get("/v1.44/info")
    except Exception as exc:  # noqa: BLE001
        return {"disponible": False, "error": str(exc)[:200]}
    return {
        "disponible": True,
        "containers": d.get("Containers"),
        "running": d.get("ContainersRunning"),
        "stopped": d.get("ContainersStopped"),
        "imagenes": d.get("Images"),
        "version_servidor": d.get("ServerVersion"),
        "kernel": d.get("KernelVersion"),
    }


def listar() -> list[dict[str, Any]]:
    """Lista de containers con estado simplificado. Vacío si no hay socket."""
    if not disponible():
        return []
    try:
        rows = _get("/v1.44/containers/json?all=1")
    except Exception:
        return []
    out = []
    for r in rows or []:
        names = r.get("Names") or []
        nombre = (names[0] if names else "").lstrip("/")
        out.append({
            "id": (r.get("Id") or "")[:12],
            "nombre": nombre,
            "imagen": r.get("Image"),
            "estado": r.get("State"),  # running, exited, ...
            "estado_humano": r.get("Status"),
            "creado_ts": r.get("Created"),
        })
    return out


def snapshot() -> dict[str, Any]:
    return {"info": info(), "containers": listar()}

# ── Estadísticas por contenedor ───────────────────────────────────────────────
# El endpoint `/stats` de Docker, con `stream=false` a secas, **espera ~1 segundo**
# porque toma DOS muestras para poder calcular el CPU. Con seis contenedores eso
# son seis segundos por refresco: inservible para una pantalla en vivo.
#
# `one-shot=true` responde al instante, pero deja `precpu_stats` en cero y el CPU
# no se puede derivar de una sola muestra. La salida: guardar la muestra anterior
# en el proceso y calcular el delta contra ella — que es exactamente lo que hace
# `docker stats`. El primer refresco tras arrancar muestra CPU en blanco; del
# segundo en adelante, real.
# Los nombres de contenedor son estériles («despacho-gerencia», «postgres») y no
# dicen nada a quien mira la pared. Cada pieza de El Despacho tiene su nombre y
# su oficio: se muestran ésos, con el técnico disponible por si hace falta.
_PIEZAS: tuple[tuple[str, str, str], ...] = (
    # (fragmento del nombre del contenedor, cómo se llama, qué hace)
    ("el-taller",       "El Taller",     "donde trabaja el equipo"),
    ("gerencia",        "La Gerencia",   "ajustes y catálogos"),
    ("recepcion",       "La Recepción",  "portal de clientes"),
    ("mostrador",       "El Mostrador",  "entrega las fotos"),
    ("portavoz",        "El Portavoz",   "avisa a los sistemas de fuera"),
    ("postgres",        "El Archivero",  "guarda todo"),
    ("redis",           "La Libreta",    "notas rápidas y la cola"),
    ("portero",         "El Portero",    "recibe de internet"),
)


def bautizar(nombre_contenedor: str) -> tuple[str, str]:
    """De «despacho-gerencia» a («La Gerencia», «ajustes y catálogos»)."""
    n = (nombre_contenedor or "").lower()
    for fragmento, nombre, oficio in _PIEZAS:
        if fragmento in n:
            return nombre, oficio
    return nombre_contenedor, ""


_MUESTRA_PREVIA: dict[str, tuple[int, int]] = {}


def _pct_cpu(clave: str, cpu_total: int, sistema_total: int, nucleos: int) -> float | None:
    previa = _MUESTRA_PREVIA.get(clave)
    _MUESTRA_PREVIA[clave] = (cpu_total, sistema_total)
    if previa is None:
        return None
    d_cpu = cpu_total - previa[0]
    d_sistema = sistema_total - previa[1]
    if d_cpu <= 0 or d_sistema <= 0:
        return 0.0
    return round((d_cpu / d_sistema) * max(nucleos, 1) * 100.0, 1)


def estadisticas(ids: list[str] | None = None, *, timeout: float = 3.0) -> list[dict[str, Any]]:
    """CPU y memoria por contenedor, al estilo `docker stats`. Nunca lanza.

    Se consultan en paralelo: son llamadas independientes al socket y en serie
    sumarían. Un contenedor que no responda sale con sus cifras en `None` en vez
    de tumbar el panel completo.
    """
    if not disponible():
        return []
    corriendo = [c for c in listar() if c.get("estado") == "running"]
    if ids:
        corriendo = [c for c in corriendo if c["id"] in ids]
    if not corriendo:
        return []

    def una(c: dict[str, Any]) -> dict[str, Any]:
        nombre_bonito, oficio = bautizar(c["nombre"])
        fila = {"id": c["id"], "nombre": c["nombre"],
                "pieza": nombre_bonito, "oficio": oficio,
                "cpu_pct": None, "mem_mb": None, "mem_pct": None,
                "mem_limite_mb": None}
        try:
            d = _get(f"/v1.44/containers/{c['id']}/stats?stream=false&one-shot=true",
                     timeout=timeout)
        except Exception:  # noqa: BLE001 — un contenedor mudo no tumba el panel
            return fila
        if not isinstance(d, dict):
            return fila
        cpu = d.get("cpu_stats") or {}
        uso = (cpu.get("cpu_usage") or {}).get("total_usage")
        sistema = cpu.get("system_cpu_usage")
        nucleos = cpu.get("online_cpus") or 1
        if isinstance(uso, int) and isinstance(sistema, int):
            fila["cpu_pct"] = _pct_cpu(c["id"], uso, sistema, nucleos)
        mem = d.get("memory_stats") or {}
        usado = mem.get("usage")
        limite = mem.get("limit")
        # Docker cuenta el caché de archivos dentro de `usage`; `docker stats` lo
        # descuenta para no reportar como "usado" lo que el kernel puede soltar.
        cache = (mem.get("stats") or {}).get("inactive_file") or 0
        if isinstance(usado, int):
            neto = max(usado - cache, 0)
            fila["mem_mb"] = round(neto / 1048576, 1)
            if isinstance(limite, int) and limite > 0:
                fila["mem_limite_mb"] = round(limite / 1048576, 1)
                fila["mem_pct"] = round(neto / limite * 100, 1)
        return fila

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=min(8, len(corriendo))) as pool:
        filas = list(pool.map(una, corriendo))
    # Lo que más consume, arriba: es lo que se quiere ver de un vistazo.
    filas.sort(key=lambda f: (f["cpu_pct"] or 0, f["mem_mb"] or 0), reverse=True)
    return filas
