"""Las Capacidades — registro único de tools del Chalán (S-Chalan-MCP-V1).

API pública:
  - `listar(usuario, modos)`        → capacidades visibles (gateadas) por modo.
  - `ejecutar(nombre, args, usuario)`→ valida + gatea + corre + recorta (lecturas).
  - `specs_chat(usuario, modos)`    → specs para `Adapter.chatear`.
  - `CAPACIDADES`                   → registro crudo (whitelist físico).

Importar este paquete registra las capacidades de lectura (`lecturas`) y, cuando
exista, las de propuesta (`propuestas`).
"""

from __future__ import annotations

from . import lecturas  # noqa: F401,E402 — registra capacidades de lectura
from .gating import gate_ok
from .registro import (
    CAPACIDADES,
    MAX_CHARS_TOOL,
    MODO_LECTURA,
    MODO_PROPUESTA,
    Capacidad,
    recortar,
    registrar,
    validar_args,
)


def listar(usuario, modos: tuple[str, ...] = (MODO_LECTURA,)) -> list[Capacidad]:
    """Capacidades del/los `modos` pedidos, filtradas por gating del usuario."""
    return [c for c in CAPACIDADES.values() if c.modo in modos and gate_ok(c.gating, usuario)]


def ejecutar(nombre: str, args: dict, usuario) -> dict:
    """Ejecuta una capacidad de LECTURA: whitelist + gating + args + recorte.

    Nunca lanza. Para capacidades de propuesta el orquestador NO llama aquí a
    mutar — recolecta la propuesta (ver `capacidades.propuestas`)."""
    cap = CAPACIDADES.get(nombre)
    if cap is None:
        return {"error": "herramienta_inexistente", "nombre": nombre}
    if not gate_ok(cap.gating, usuario):
        return {"error": "sin_permiso", "nombre": nombre}
    try:
        limpios = validar_args(cap, args or {})
    except ValueError as exc:
        return {"error": "args_invalidos", "detalle": str(exc)}
    try:
        salida = cap.fn(limpios, usuario)
    except Exception as exc:  # noqa: BLE001 — una capacidad nunca tumba el chat
        return {"error": "fallo_herramienta", "detalle": str(exc)[:200]}
    return recortar(salida)


def specs_chat(usuario, modos: tuple[str, ...] = (MODO_LECTURA,)) -> list[dict]:
    from .mcp_schema import spec_chat
    return [spec_chat(c) for c in listar(usuario, modos)]


__all__ = [
    "CAPACIDADES", "Capacidad", "MODO_LECTURA", "MODO_PROPUESTA",
    "gate_ok", "registrar", "validar_args", "recortar", "MAX_CHARS_TOOL",
    "listar", "ejecutar", "specs_chat",
]
