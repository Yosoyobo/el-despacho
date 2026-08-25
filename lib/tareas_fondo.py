"""Trabajo que no tiene por qué hacer esperar a quien mandó la petición.

El caso que lo motivó: enviar un mensaje en el chat tardaba **2.8 segundos**
(medido en producción el 2026-08-24). El mensaje se guardaba en milisegundos;
lo que tardaba era que el servidor esperaba a que Apple y Google acusaran
recibo de las notificaciones, una por una, abriendo conexión nueva cada vez
(160-230 ms a Apple, 80-100 ms a Google, medidos desde el NUC). Con ocho
dispositivos registrados, la persona miraba la pantalla quieta casi tres
segundos por algo que no le importa: que al OTRO le suene el teléfono.

Aquí no va nada que el usuario necesite ver confirmado. La regla para decidir
si algo puede correr en el fondo:

- Va al fondo lo que **avisa a terceros** (push, correo de cortesía) y lo que
  la pantalla no muestra de vuelta.
- Se queda en la petición todo lo que el usuario va a ver: lo que se guarda,
  lo que se le responde, y cualquier cosa cuyo fallo tenga que enterarse.

El precio, dicho de frente: si el trabajador de gunicorn se recicla justo
mientras un aviso está en vuelo, ese aviso no sale. Es una ventana de
milisegundos y sólo afecta a la notificación — nunca al dato, que ya se
guardó y confirmó antes. Por eso el registro del aviso en el historial del
Interfón se escribe ANTES de mandar nada al fondo.

En las pruebas corre todo síncrono (`TAREAS_EN_FONDO = False` en el settings
de pruebas): un hilo suelto haría que los tests compitieran contra él.
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Ocho a la vez alcanza de sobra: lo que corre aquí es I/O (espera de red), no
# cuentas. El tope existe para que una racha de avisos no abra hilos sin freno.
MAX_HILOS = 8

_pool: ThreadPoolExecutor | None = None
_candado = threading.Lock()


def _obtener_pool() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        with _candado:
            if _pool is None:
                _pool = ThreadPoolExecutor(
                    max_workers=MAX_HILOS, thread_name_prefix="despacho-fondo"
                )
                atexit.register(_apagar)
    return _pool


def _apagar() -> None:
    """Deja terminar lo que esté en vuelo cuando el proceso se va."""
    global _pool
    pool, _pool = _pool, None
    if pool is not None:
        with contextlib.suppress(Exception):
            pool.shutdown(wait=True, cancel_futures=False)


def _en_fondo_activo() -> bool:
    try:
        from django.conf import settings

        return bool(getattr(settings, "TAREAS_EN_FONDO", True))
    except Exception:
        return False


def _correr(fn: Callable, *args, **kwargs) -> None:
    """Ejecuta y limpia. Nunca deja escapar una excepción: si tumbara el hilo,
    el error saldría en un sitio que nadie mira y sin contexto de la petición."""
    try:
        fn(*args, **kwargs)
    except Exception:
        logger.exception("tarea de fondo falló: %s", getattr(fn, "__name__", fn))
    finally:
        # Un hilo nuevo abre su propia conexión a Postgres. Con CONN_MAX_AGE=60
        # se quedaría reservada un minuto sin que nadie la use; con muchos avisos
        # eso son conexiones desperdiciadas del cupo del servidor.
        try:
            from django.db import connections

            connections.close_all()
        except Exception:
            logger.exception("tarea de fondo: no pude cerrar conexiones")


def ejecutar_en_fondo(fn: Callable, *args, **kwargs) -> None:
    """Corre `fn` sin hacer esperar a la petición en curso.

    Nunca lanza: si el trabajo falla, queda en la bitácora y la petición sigue
    su camino como si nada — que es justo lo que se quiere de un aviso.
    """
    if not _en_fondo_activo():
        _correr(fn, *args, **kwargs)
        return
    try:
        _obtener_pool().submit(_correr, fn, *args, **kwargs)
    except Exception:
        # Pool saturado o apagándose: mejor tarde y en la petición que nunca.
        logger.exception("tarea de fondo: no pude encolar, corro síncrono")
        _correr(fn, *args, **kwargs)


__all__ = ["ejecutar_en_fondo", "MAX_HILOS"]
