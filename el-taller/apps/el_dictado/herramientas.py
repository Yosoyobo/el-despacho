"""Compat shim — el registro de herramientas del Chalán vive ahora en el paquete
raíz `capacidades` (S-Chalan-MCP-V1).

Se conserva este módulo para importadores y tests históricos que hacen
`apps.el_dictado.herramientas.<símbolo>`. Todo delega en `capacidades`.
"""

from __future__ import annotations

from capacidades import (
    CAPACIDADES,
    MAX_CHARS_TOOL,
    MODO_LECTURA,
    recortar,
    validar_args,
)
from capacidades import ejecutar as ejecutar_herramienta
from capacidades import listar as _listar
from capacidades.gating import gate_ok as _gate_ok

# Impls usadas directamente por algunos tests/módulos.
from capacidades.lecturas import _h_detalle_proyecto, _h_mis_tareas  # noqa: F401
from capacidades.registro import _TOP_N
from capacidades.registro import Capacidad as Herramienta

# Snapshot de solo-lectura (equivale al viejo `HERRAMIENTAS`, que solo tenía
# lecturas). Las capacidades de propuesta NO entran aquí.
HERRAMIENTAS = {n: c for n, c in CAPACIDADES.items() if c.modo == MODO_LECTURA}

__all__ = [
    "HERRAMIENTAS", "Herramienta", "herramientas_para", "ejecutar_herramienta",
    "validar_args", "recortar", "_gate_ok", "_TOP_N", "MAX_CHARS_TOOL",
    "_h_detalle_proyecto", "_h_mis_tareas",
]


def herramientas_para(usuario):
    """Herramientas de lectura visibles para el usuario (compat)."""
    return _listar(usuario, modos=(MODO_LECTURA,))
