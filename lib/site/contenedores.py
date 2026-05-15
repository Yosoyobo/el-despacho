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
