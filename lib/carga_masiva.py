"""La bandera de «carga masiva en curso» (S-Carga-Contable).

La carga de la contabilidad histórica crea de un jalón cientos de ingresos,
gastos y facturas. Dos cosas de la captura normal estorban ahí:

1. **Los avisos a terceros.** Un ingreso con cliente dispara el correo «recibimos
   tu pago»; un cliente nuevo, el de bienvenida. Importar un pago de marzo no es
   recibirlo hoy: mandar ese correo sería mentirle al cliente.
2. **Los asientos diferidos.** La Contaduría arma sus asientos con
   `transaction.on_commit`, así que dentro de una transacción que se deshace
   (la vista previa) nunca existen, y la vista previa no podría enseñar cómo
   queda el balance. Con la bandera puesta, el asiento se escribe en el acto,
   dentro de la misma transacción: se confirma con ella o se deshace con ella.

Es una `ContextVar`, no un global: gunicorn corre hilos y la carga de uno no
debe silenciar la captura del otro.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_EN_CARGA: ContextVar[bool] = ContextVar("despacho_carga_masiva", default=False)


def en_carga() -> bool:
    """¿Estamos dentro de una carga masiva?"""
    return _EN_CARGA.get()


@contextmanager
def carga_masiva() -> Iterator[None]:
    """Marca el bloque como carga masiva (anidable)."""
    token = _EN_CARGA.set(True)
    try:
        yield
    finally:
        _EN_CARGA.reset(token)


def diferir(fn: Callable[[], object]) -> None:
    """`transaction.on_commit(fn)` en la captura normal; `fn()` en el acto
    dentro de una carga masiva (ver el punto 2 del docstring del módulo)."""
    if en_carga():
        fn()
        return
    from django.db import transaction

    transaction.on_commit(fn)
