"""Capacidad → specs de tool para cada consumidor.

- `spec_chat`  → formato canónico del repo `{nombre, descripcion, args_schema}`
  que consume `Adapter.chatear` (function-calling nativo interno).
- `tool_mcp`   → `{name, description, inputSchema}` (JSON Schema) para el
  servidor MCP por stdio `mcp_despacho`.

El puente `args_schema` → JSON Schema reutiliza `esquema_json` de
`lib.analistas.herramientas_formato`, la misma pieza que ya traduce al
function-calling de cada proveedor.
"""

from __future__ import annotations

from .registro import Capacidad


def spec_chat(cap: Capacidad) -> dict:
    return {"nombre": cap.nombre, "descripcion": cap.descripcion, "args_schema": cap.args_schema}


def json_schema(cap: Capacidad) -> dict:
    from lib.analistas.herramientas_formato import esquema_json
    return esquema_json(cap.args_schema)


def tool_mcp(cap: Capacidad) -> dict:
    return {"name": cap.nombre, "description": cap.descripcion, "inputSchema": json_schema(cap)}
