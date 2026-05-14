"""Worker que desencola eventos del Portavoz y los postea a n8n con HMAC.

Corre como servicio aparte en Docker Compose (`portavoz-worker`).
Lee la URL y el secret desde Los Ajustes (DB cifrados); si no existen aún,
duerme y reintenta — los eventos quedan encolados sin pérdida.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time

import django
import httpx
import redis

logger = logging.getLogger("portavoz.worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _init_django():
    """El worker comparte la DB con La Gerencia para leer Los Ajustes."""
    sys.path.insert(0, "/app")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "la_gerencia.settings")
    django.setup()


def _leer_credenciales_n8n():
    """Lee (url, secret) desde Los Ajustes. Devuelve (None, None) si faltan."""
    from ajustes.models.credencial import Credencial

    try:
        url = Credencial.obtener("n8n_webhook_url")
        secret = Credencial.obtener("n8n_webhook_secret")
    except Exception:
        return None, None
    return url, secret


def _postear(url: str, secret: str, payload_bytes: bytes) -> int:
    from lib.portavoz import firmar

    firma = firmar(payload_bytes, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Despacho-Signature": firma,
    }
    with httpx.Client(timeout=10.0) as cli:
        r = cli.post(url, content=payload_bytes, headers=headers)
        return r.status_code


def main():
    _init_django()
    from lib.portavoz import COLA

    r = redis.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        decode_responses=True,
    )
    logger.info("Portavoz worker arrancado. Esperando eventos en %s …", COLA)

    while True:
        try:
            item = r.blpop(COLA, timeout=5)
        except redis.RedisError as exc:
            logger.error("Redis fallo: %s — durmiendo 5s", exc)
            time.sleep(5)
            continue

        if not item:
            continue
        _, raw = item

        url, secret = _leer_credenciales_n8n()
        if not url or not secret:
            logger.warning("Sin credenciales de n8n; re-encolo y duermo 30s.")
            r.rpush(COLA, raw)
            time.sleep(30)
            continue

        try:
            payload = raw.encode("utf-8") if isinstance(raw, str) else raw
            evento_tipo = json.loads(raw).get("tipo", "?")
            status = _postear(url, secret, payload)
            if status >= 400:
                logger.error("n8n %s para evento %s — re-encolo", status, evento_tipo)
                r.rpush(COLA, raw)
                time.sleep(10)
            else:
                logger.info("Evento %s entregado (HTTP %s)", evento_tipo, status)
        except Exception as exc:
            logger.exception("Fallo entregando evento: %s — re-encolo", exc)
            r.rpush(COLA, raw)
            time.sleep(10)


if __name__ == "__main__":
    main()
