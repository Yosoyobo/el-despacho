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


def _gate(usuario, helper: str, accion_humana: str) -> None:
    """Defensa en profundidad: re-chequea el permiso del usuario antes de
    escribir, aunque el prompt ya enumere solo lo permitido por rol
    (`dictado_catalogo.comandos_para`). El Chalán nunca aplica sin
    confirmación humana, pero esto garantiza que un rol sin permiso no escriba
    aunque el LLM proponga la acción. `helper` es el nombre de la función en
    `lib.permisos`."""
    from lib import permisos
    if not getattr(permisos, helper)(usuario):
        raise ValueError(f"No tienes permiso para {accion_humana}.")


from . import (  # noqa: F401, E402 — registra ejecutores al importar
    avanzados,
    basicos,
    catalogo,
    checador,
)

__all__ = ["EJECUTORES", "registrar", "_gate"]
