"""Aviso "deploy en curso" — bandera en Redis para mostrar banner en las 3 apps.

Flujo:
- `mudanza.sh` llama `marcar_deploy_en_curso(commit_sha)` ANTES de
  `docker compose up -d`.
- El banner aparece en las 3 apps mientras `obtener_deploy_en_curso()`
  retorne valor.
- `mudanza.sh` llama `limpiar_deploy_en_curso()` después del healthcheck verde.
- TTL de 600s como red de seguridad por si el script muere a media corrida.

Dos niveles (S-NUC-Servicios, 2026-08-24):

- **ámbar** — hay una ventana de mantenimiento abierta. El sistema funciona
  normal; el banner sólo avisa que hoy se está trabajando en la plataforma.
- **rojo** — además, algo NO está respondiendo ahora mismo. Se enciende
  solo: nadie tiene que acordarse de marcarlo antes de un corte.

El rojo se calcula con sondas baratas y **el resultado se cachea en Redis**,
no por proceso: el banner lo pide cada 10 segundos desde cada pestaña
abierta, así que sin caché compartido el costo se multiplicaría por el
número de personas mirando. Con caché, son unas pocas sondas por minuto
sin importar cuánta gente haya.

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

CLAVE_NIVEL = "despacho:aviso:nivel"
TTL_NIVEL = 20  # segundos que dura el veredicto de las sondas

NIVEL_AMBAR = "ambar"
NIVEL_ROJO = "rojo"

#: Centinela para distinguir «no me pasaron la bandera» de «no hay bandera».
_SIN_LEER = object()

#: Servicios que se sondean para decidir el rojo. Se leen de `AVISO_SONDAS`
#: (URLs separadas por coma) para poder sumar los servicios nuevos del NUC
#: sin tocar este archivo.
TIMEOUT_SONDA = 2.0

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


def _sondas_configuradas() -> list[str]:
    """URLs a sondear, de la variable `AVISO_SONDAS`. Vacío = sólo la base."""
    crudo = os.environ.get("AVISO_SONDAS", "")
    return [u.strip() for u in crudo.split(",") if u.strip()]


def _base_responde() -> bool:
    """`SELECT 1` contra Postgres. Cualquier tropiezo cuenta como caída."""
    try:
        from django.db import connection

        connection.ensure_connection()
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as exc:  # noqa: BLE001 — cualquier fallo es "no responde"
        logger.warning("aviso_deploy: la base no responde: %s", exc)
        return False


def _servicio_responde(url: str) -> bool:
    """HTTP GET corto. Un 5xx cuenta como caída; un 4xx no (contestó)."""
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=TIMEOUT_SONDA) as r:
            return r.status < 500
    except Exception as exc:  # noqa: BLE001
        logger.warning("aviso_deploy: %s no responde: %s", url, exc)
        return False


def _calcular_nivel() -> str:
    """Ámbar por defecto; rojo si algo no contesta."""
    if not _base_responde():
        return NIVEL_ROJO
    for url in _sondas_configuradas():
        if not _servicio_responde(url):
            return NIVEL_ROJO
    return NIVEL_AMBAR


def nivel_aviso(sha: str | None = _SIN_LEER) -> str | None:
    """Nivel del banner: `ambar`, `rojo`, o None si no hay ventana abierta.

    El veredicto se guarda en Redis unos segundos (`TTL_NIVEL`) para que el
    polling de todas las pestañas comparta el mismo trabajo.

    `sha` permite pasar la bandera ya leída. Esto corre en el context
    processor, o sea en CADA petición de las tres apps: releerla aquí
    duplicaría el viaje a Redis del camino caliente sin ganar nada.
    """
    if sha is _SIN_LEER:
        sha = obtener_deploy_en_curso()
    if not sha:
        return None
    try:
        cli = _client()
        cacheado = cli.get(CLAVE_NIVEL)
        if cacheado in (NIVEL_AMBAR, NIVEL_ROJO):
            return cacheado
        nivel = _calcular_nivel()
        cli.set(CLAVE_NIVEL, nivel, ex=TTL_NIVEL)
        return nivel
    except (RedisConnectionError, RedisTimeoutError) as exc:
        # Redis caído ES una caída: si la ventana está abierta, es rojo.
        logger.warning("aviso_deploy.nivel falló: %s", exc)
        return NIVEL_ROJO


def contexto_aviso_deploy(request) -> dict:
    """Context processor: expone `hay_deploy_en_curso` y `deploy_commit_sha`.

    Registrar en `TEMPLATES.OPTIONS.context_processors` de los 3 settings.
    """
    sha = obtener_deploy_en_curso()
    return {
        "hay_deploy_en_curso": bool(sha),
        "deploy_commit_sha": sha,
        "nivel_aviso": nivel_aviso(sha),
    }


__all__ = [
    "CLAVE_REDIS",
    "CLAVE_NIVEL",
    "NIVEL_AMBAR",
    "NIVEL_ROJO",
    "TTL_DEFAULT",
    "TTL_NIVEL",
    "nivel_aviso",
    "marcar_deploy_en_curso",
    "limpiar_deploy_en_curso",
    "obtener_deploy_en_curso",
    "contexto_aviso_deploy",
]
