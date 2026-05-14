"""El Portavoz — emite eventos tipados a n8n vía webhook firmado con HMAC-SHA256.

Encola en Redis (`portavoz:cola`) en vez de hacer POST en línea, para no acoplar
latencia de Django a la disponibilidad de n8n. El worker (`portavoz_worker.py`)
desencola y postea.

La URL y el secret del webhook viven en Los Ajustes (cifrados con La Bóveda).
Si no están configurados, `emitir()` igual encola — el worker hará retry hasta
que el slot esté listo.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import redis

from .errors import PortavozError
from .portavoz_eventos import EventoPortavoz

COLA = "portavoz:cola"

_redis_client: redis.Redis | None = None


def _client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.Redis.from_url(url, decode_responses=True)
    return _redis_client


def emitir(evento: EventoPortavoz) -> None:
    """Encola un evento. Idempotente al level del worker (cada mensaje tiene id)."""
    if not isinstance(evento, EventoPortavoz):
        raise PortavozError("emitir() solo acepta instancias de EventoPortavoz")
    try:
        _client().rpush(COLA, json.dumps(evento.serializar(), ensure_ascii=False))
    except redis.RedisError as exc:
        raise PortavozError(f"Redis rechazó el encolado: {exc}") from exc


def firmar(payload: bytes, secret: str) -> str:
    """HMAC-SHA256 sobre el body crudo. Header esperado en n8n: `X-Despacho-Signature`."""
    if not secret:
        raise PortavozError("Secret vacío al firmar")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verificar(payload: bytes, secret: str, firma: str) -> bool:
    """Verifica una firma recibida (útil para webhooks ENTRANTES si fueran necesarios)."""
    if not firma:
        return False
    esperado = firmar(payload, secret)
    return hmac.compare_digest(esperado, firma)
