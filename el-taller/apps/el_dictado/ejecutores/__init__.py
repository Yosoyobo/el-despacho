"""Ejecutores por tipo de acción (DOC_04 §8).

Cada ejecutor toma `(accion, usuario)` y aplica el cambio en el sistema.
Lanza excepción si falla — `aplicar_dictado()` la captura y persiste en
`accion.error_al_aplicar`. NUNCA aborta el resto de las acciones.

Ejecutores activos: actualizar_proyecto, asignar_usuario_proyecto,
crear_tarea, actualizar_tarea, crear_recado, crear_mensaje_buzon,
registrar_egreso (S2b.3). `registrar_ingreso` queda pendiente — los
dictados de cobro son raros y casi siempre tienen factura referenciada;
se agrega cuando un caso real lo pida.
"""

from __future__ import annotations

from collections.abc import Callable

EJECUTORES: dict[str, Callable] = {}


def registrar(tipo: str):
    def deco(func):
        EJECUTORES[tipo] = func
        return func
    return deco


from . import avanzados, basicos, checador  # noqa: F401, E402 — registra ejecutores al importar

__all__ = ["EJECUTORES", "registrar"]
