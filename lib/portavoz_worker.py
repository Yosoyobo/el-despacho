"""Worker que desencola eventos del Portavoz y los postea a n8n con HMAC.

Corre como servicio aparte en Docker Compose (`portavoz-worker`).
Lee la URL y el secret desde Los Ajustes (DB cifrados); si no existen aún,
duerme y reintenta — los eventos quedan encolados sin pérdida.

Dead-letter queue: cada evento lleva `_intentos` en su JSON. Tras
`MAX_INTENTOS` fallos, se descarta a `portavoz:fallidos` (lista Redis)
para inspección posterior con `python manage.py portavoz_fallidos`.
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

COLA = "portavoz:cola"
DLQ = "portavoz:fallidos"
MAX_INTENTOS = 5
ESPERA_FALLA_SEG = 10
ESPERA_SIN_CREDS_SEG = 30


def _init_django():
    """El worker comparte la DB con La Gerencia para leer Los Ajustes."""
    sys.path.insert(0, "/app")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "la_gerencia.settings")
    django.setup()


def _leer_credenciales_n8n():
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
    headers = {"Content-Type": "application/json", "X-Despacho-Signature": firma}
    with httpx.Client(timeout=10.0) as cli:
        r = cli.post(url, content=payload_bytes, headers=headers)
        return r.status_code


def _reencolar_con_intento(r: redis.Redis, raw: str) -> int:
    """Incrementa `_intentos` en el JSON y re-encola si <MAX_INTENTOS,
    o descarta a DLQ si se agotó. Devuelve el nuevo contador de intentos."""
    try:
        evt = json.loads(raw)
    except json.JSONDecodeError:
        # JSON corrupto — al DLQ de inmediato.
        r.rpush(DLQ, raw)
        logger.error("JSON corrupto descartado a DLQ.")
        return MAX_INTENTOS + 1

    intentos = int(evt.get("_intentos", 0)) + 1
    evt["_intentos"] = intentos
    nuevo_raw = json.dumps(evt, ensure_ascii=False)

    if intentos >= MAX_INTENTOS:
        r.rpush(DLQ, nuevo_raw)
        logger.error(
            "Evento %s agotó %d intentos — descartado a %s.",
            evt.get("tipo", "?"),
            intentos,
            DLQ,
        )
    else:
        r.rpush(COLA, nuevo_raw)
        logger.warning(
            "Re-encolando evento %s (intento %d/%d)",
            evt.get("tipo", "?"),
            intentos,
            MAX_INTENTOS,
        )
    return intentos


def main():
    _init_django()

    r = redis.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        decode_responses=True,
    )
    logger.info("Portavoz worker arrancado. COLA=%s DLQ=%s MAX_INTENTOS=%d", COLA, DLQ, MAX_INTENTOS)

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
            logger.warning("Sin credenciales de n8n; re-encolo (sin contar intento) y duermo %ds.", ESPERA_SIN_CREDS_SEG)
            r.rpush(COLA, raw)
            time.sleep(ESPERA_SIN_CREDS_SEG)
            continue

        try:
            payload = raw.encode("utf-8") if isinstance(raw, str) else raw
            evt = json.loads(raw)
            evento_tipo = evt.get("tipo", "?")
            status = _postear(url, secret, payload)
            if status >= 400:
                logger.error("n8n %s para evento %s", status, evento_tipo)
                _reencolar_con_intento(r, raw)
                time.sleep(ESPERA_FALLA_SEG)
            else:
                logger.info("Evento %s entregado (HTTP %s)", evento_tipo, status)
        except Exception as exc:
            logger.exception("Fallo entregando evento: %s", exc)
            _reencolar_con_intento(r, raw)
            time.sleep(ESPERA_FALLA_SEG)


if __name__ == "__main__":
    main()
