"""Rate-limit con Redis (sliding window). Regla #5: login 5 intentos / 15 min."""

from __future__ import annotations

import os
import time

import redis

from .errors import RateLimitExcedido

_redis_client: redis.Redis | None = None


def _client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.Redis.from_url(url, decode_responses=True)
    return _redis_client


def intentar(scope: str, identidad: str, *, limite: int, ventana_seg: int) -> int:
    """Registra un intento. Devuelve el contador actual.
    Lanza RateLimitExcedido si supera `limite` dentro de `ventana_seg`.
    """
    key = f"ratelimit:{scope}:{identidad}"
    now = int(time.time())
    desde = now - ventana_seg
    pipe = _client().pipeline()
    pipe.zremrangebyscore(key, 0, desde)
    pipe.zadd(key, {f"{now}:{os.urandom(4).hex()}": now})
    pipe.zcard(key)
    pipe.expire(key, ventana_seg + 5)
    _, _, count, _ = pipe.execute()
    if count > limite:
        raise RateLimitExcedido(
            f"Demasiados intentos para {scope}. Espera unos minutos."
        )
    return int(count)


def reset(scope: str, identidad: str) -> None:
    _client().delete(f"ratelimit:{scope}:{identidad}")
