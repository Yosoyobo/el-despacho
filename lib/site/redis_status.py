"""Redis — chequeo PING + items en la cola del Portavoz + items en DLQ."""

from __future__ import annotations

import os
import time
from typing import Any

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
COLA_PORTAVOZ = "portavoz:cola"
COLA_FALLIDOS = "portavoz:fallidos"


def _cliente():
    import redis
    return redis.Redis.from_url(REDIS_URL, socket_connect_timeout=2)


def chequear() -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        ok = bool(_cliente().ping())
    except Exception as exc:  # noqa: BLE001
        return {"estado": "error", "mensaje_error": str(exc)[:200], "latencia_ms": int((time.monotonic() - t0) * 1000)}
    return {"estado": "ok" if ok else "error", "latencia_ms": int((time.monotonic() - t0) * 1000)}


def detalles() -> dict[str, Any]:
    try:
        c = _cliente()
        info = c.info(section="memory")
        cola = c.llen(COLA_PORTAVOZ)
        dlq = c.llen(COLA_FALLIDOS)
    except Exception as exc:  # noqa: BLE001
        return {"disponible": False, "error": str(exc)[:200]}
    used = info.get("used_memory", 0)
    return {
        "disponible": True,
        "memoria_mb": round(used / (1024 * 1024), 2) if used else 0,
        "portavoz_cola": int(cola or 0),
        "portavoz_dlq": int(dlq or 0),
    }
