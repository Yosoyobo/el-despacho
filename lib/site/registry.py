"""Registry de plataformas chequeables. Para agregar una nueva, define una
función `def chequear() -> dict` que retorne `{estado, latencia_ms, mensaje_error?}`
y agrégala al diccionario `PLATAFORMAS`.

Cada chequeo es síncrono y debe completar en < 10 s (timeouts internos).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import droplet, integraciones, postgres, redis_status

# El estado del chequeo siempre es uno de:
ESTADOS = ("ok", "error", "no_configurada")


PLATAFORMAS: dict[str, Callable[[], dict[str, Any]]] = {
    "anthropic": integraciones.chequear_anthropic,
    "openai": integraciones.chequear_openai,
    "do_api": droplet.chequear,
    "postgres": postgres.chequear,
    "redis": redis_status.chequear,
    "docker": integraciones.chequear_docker,
    "tailscale": integraciones.chequear_tailscale,
    "n8n_tailscale": integraciones.chequear_n8n,
}


def chequear(plataforma: str) -> dict[str, Any]:
    fn = PLATAFORMAS.get(plataforma)
    if fn is None:
        return {"estado": "error", "mensaje_error": f"plataforma desconocida: {plataforma}"}
    try:
        res = fn()
    except Exception as exc:  # noqa: BLE001
        return {"estado": "error", "mensaje_error": str(exc)[:200], "latencia_ms": None}
    # Normaliza
    res.setdefault("estado", "error")
    res.setdefault("latencia_ms", None)
    res.setdefault("mensaje_error", None)
    return res


def chequear_todas() -> dict[str, dict[str, Any]]:
    return {p: chequear(p) for p in PLATAFORMAS}
