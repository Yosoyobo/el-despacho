"""Aviso "deploy en curso" — bandera en Redis para mostrar banner en las 3 apps.

Flujo:
- `mudanza.sh` llama `marcar_deploy_en_curso(commit_sha)` ANTES de
  `docker compose up -d`.
- El banner aparece en las 3 apps mientras `obtener_deploy_en_curso()`
  retorne valor.
- `mudanza.sh` llama `limpiar_deploy_en_curso()` después del healthcheck verde.
- TTL de 600s como red de seguridad por si el script muere a media corrida.

Si Redis está caído, `obtener_deploy_en_curso()` devuelve None (no mostramos
banner) — Redis caído es problema más grande que merece su propia alerta
del Site, no rompemos la página por intentar mostrar el aviso.
"""

from __future__ import annotations

import logging
import os

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

CLAVE_REDIS = "despacho:deploy:en_curso"
TTL_DEFAULT = 600  # 10 minutos — red de seguridad si el script muere.

logger = logging.getLogger(__name__)
_redis_client: redis.Redis | None = None


def _client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
    return _redis_client


def marcar_deploy_en_curso(commit_sha: str, ttl_segundos: int = TTL_DEFAULT) -> None:
    """Setea la bandera en Redis con TTL. No lanza si Redis está caído."""
    try:
        _client().set(CLAVE_REDIS, commit_sha or "?", ex=ttl_segundos)
    except (RedisConnectionError, RedisTimeoutError) as exc:
        logger.warning("aviso_deploy.marcar falló: %s", exc)


def limpiar_deploy_en_curso() -> None:
    """Borra la bandera. No lanza si Redis está caído."""
    try:
        _client().delete(CLAVE_REDIS)
    except (RedisConnectionError, RedisTimeoutError) as exc:
        logger.warning("aviso_deploy.limpiar falló: %s", exc)


def obtener_deploy_en_curso() -> str | None:
    """Retorna el SHA del commit en deploy, o None si no hay / Redis caído."""
    try:
        return _client().get(CLAVE_REDIS)
    except (RedisConnectionError, RedisTimeoutError) as exc:
        logger.warning("aviso_deploy.obtener falló: %s", exc)
        return None


def contexto_aviso_deploy(request) -> dict:
    """Context processor: expone `hay_deploy_en_curso` y `deploy_commit_sha`.

    Registrar en `TEMPLATES.OPTIONS.context_processors` de los 3 settings.
    """
    sha = obtener_deploy_en_curso()
    return {
        "hay_deploy_en_curso": bool(sha),
        "deploy_commit_sha": sha,
    }


__all__ = [
    "CLAVE_REDIS",
    "TTL_DEFAULT",
    "marcar_deploy_en_curso",
    "limpiar_deploy_en_curso",
    "obtener_deploy_en_curso",
    "contexto_aviso_deploy",
]
