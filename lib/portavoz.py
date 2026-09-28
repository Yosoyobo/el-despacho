"""El Portavoz — emite eventos tipados a n8n vía webhook firmado con HMAC-SHA256.

Encola en Redis (`portavoz:cola`) en vez de hacer POST en línea, para no acoplar
latencia de Django a la disponibilidad de n8n. El worker (`portavoz_worker.py`)
desencola y postea.

La URL y el secret del webhook viven en Los Ajustes (cifrados con La Bóveda).

**Sin destino, el Portavoz se pone en pausa** (decisión Oscar, 2026-09-28). Antes
`emitir()` encolaba igual y el worker reintentaba "hasta que el slot estuviera
listo": como nunca hubo un flujo del otro lado, la cola llegó a 5,198 eventos en
agosto y a 2,192 más en septiembre, ocupando la memoria de Redis para nada. Ahora,
si no hay `n8n_webhook_url`, no se encola: se CUENTA lo que no salió
(`portavoz:sin_destino`, con la fecha en que empezó la pausa) y El Vigía y
`/salud` lo dicen. Nada se pierde en silencio: se sabe cuántos y desde cuándo.
Si no se puede saber si hay destino (Django sin configurar, base caída), se
encola como siempre — ante la duda, no se tira nada.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import time
from datetime import UTC, datetime

import redis

from .errors import PortavozError
from .portavoz_eventos import EventoPortavoz

COLA = "portavoz:cola"
# Lo que no se encoló por falta de destino: un contador y desde cuándo.
SIN_DESTINO = "portavoz:sin_destino"
SIN_DESTINO_DESDE = "portavoz:sin_destino:desde"
# Cuánto se recuerda la respuesta de «¿hay destino?» dentro del proceso. Leer la
# credencial en cada emisión sería una consulta por evento.
TTL_DESTINO_SEG = 60

_destino_cache: tuple[float, bool] | None = None

_redis_client: redis.Redis | None = None


def _client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.Redis.from_url(url, decode_responses=True)
    return _redis_client


def hay_destino() -> bool:
    """¿Hay un webhook de n8n configurado? Cacheado `TTL_DESTINO_SEG` por proceso.

    Ante cualquier duda devuelve True: preferimos encolar de más que tirar un
    evento que sí tenía a dónde ir.
    """
    global _destino_cache
    ahora = time.monotonic()
    if _destino_cache and ahora - _destino_cache[0] < TTL_DESTINO_SEG:
        return _destino_cache[1]
    try:
        from ajustes.models.credencial import Credencial

        valor = bool((Credencial.obtener("n8n_webhook_url") or "").strip())
    except Exception:  # noqa: BLE001 — sin Django o sin base: no adivinar
        return True
    _destino_cache = (ahora, valor)
    return valor


def olvidar_destino() -> None:
    """Invalida la caché de `hay_destino()` (la llama `Credencial.guardar`)."""
    global _destino_cache
    _destino_cache = None


def reiniciar_pausa() -> None:
    """Borra el contador de la pausa (al configurar un destino). Nunca lanza."""
    with contextlib.suppress(Exception):
        _client().delete(SIN_DESTINO, SIN_DESTINO_DESDE)


def en_pausa() -> dict:
    """Estado de la pausa para El Vigía y `/salud`: nunca lanza."""
    try:
        if hay_destino():
            return {"pausado": False}
        c = _client()
        return {
            "pausado": True,
            "no_enviados": int(c.get(SIN_DESTINO) or 0),
            "desde": c.get(SIN_DESTINO_DESDE) or "",
        }
    except Exception:  # noqa: BLE001
        return {"pausado": False, "error": True}


def emitir(evento: EventoPortavoz) -> None:
    """Encola un evento. Idempotente al level del worker (cada mensaje tiene id).

    Sin destino configurado no encola: cuenta el evento como no enviado.
    """
    if not isinstance(evento, EventoPortavoz):
        raise PortavozError("emitir() solo acepta instancias de EventoPortavoz")
    try:
        if not hay_destino():
            c = _client()
            c.incr(SIN_DESTINO)
            c.set(SIN_DESTINO_DESDE, datetime.now(UTC).isoformat(timespec="seconds"), nx=True)
            return
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
