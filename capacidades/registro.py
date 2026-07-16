"""Registro único de Capacidades del Chalán (S-Chalan-MCP-V1).

Una **Capacidad** es un tool con forma MCP: `nombre` + `args_schema`
(→ JSON Schema) + `gating` + `modo` (lectura | propuesta) + impl. Es la fuente
ÚNICA que consumen las dos superficies del sistema, sin duplicar lógica:

  - El Chalán interno (dispatch en proceso, con el usuario que opera).
  - El servidor MCP por stdio `mcp_despacho` (identidad fijada por env).

Guardrails heredados de la era `el_dictado.herramientas` (no se relajan):
  - Whitelist físico (`CAPACIDADES`): un nombre inexistente nunca se ejecuta.
  - Whitelist de args (`validar_args`): claves/tipos/enums/requeridos.
  - Recorte de salida (`recortar`): top-N + cap de caracteres.
  - Las ESCRITURAS son `modo="propuesta"`: NO mutan la DB — crean un Dictado con
    preview/confirm humano (regla §20). El registro solo las describe; quien las
    "ejecuta" (el orquestador) las convierte en propuesta, nunca en efecto.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

MAX_CHARS_TOOL = 1200
_TOP_N = 5

MODO_LECTURA = "lectura"
MODO_PROPUESTA = "propuesta"


@dataclass(frozen=True)
class Capacidad:
    """Un tool con forma MCP. `fn(args: dict, usuario) -> dict` para lecturas;
    para propuestas, `fn` normaliza el payload (no muta). `gating` es una clave
    resuelta por `capacidades.gating.gate_ok`."""

    nombre: str
    descripcion: str
    # {arg: {"tipo": "str"|"int"|"bool"|"dict"|"any", "requerido": bool, "enum": [...]?}}
    args_schema: dict[str, dict]
    # "abierto" | "finanzas" | "cartera" | "cotizaciones" | "facturacion"
    # | "contaduria" | "catalogo" | ...
    gating: str
    fn: Callable[[dict, Any], dict] = field(repr=False)
    modo: str = MODO_LECTURA


CAPACIDADES: dict[str, Capacidad] = {}


def registrar(cap: Capacidad) -> Capacidad:
    """Agrega (o reemplaza por nombre) una capacidad al registro único."""
    CAPACIDADES[cap.nombre] = cap
    return cap


# ── Recorte / serialización ──────────────────────────────────────────────────

def _serializable(data: Any) -> Any:
    if isinstance(data, Decimal):
        return float(data)
    if isinstance(data, dict):
        return {k: _serializable(v) for k, v in data.items()}
    if isinstance(data, list | tuple):
        return [_serializable(v) for v in data[:_TOP_N]]
    return data


def recortar(data: Any, max_chars: int = MAX_CHARS_TOOL) -> Any:
    """Serializa, poda listas a top-N y trunca el JSON resultante."""
    limpio = _serializable(data)
    blob = json.dumps(limpio, ensure_ascii=False, default=str)
    if len(blob) <= max_chars:
        return limpio
    return {"_truncado": True, "datos": blob[:max_chars]}


# ── Validación de args ─────────────────────────────────────────────────────────

def validar_args(cap: Capacidad, args: dict) -> dict:
    """Whitelist de claves + tipos + enums + requeridos. Lanza ValueError."""
    if not isinstance(args, dict):
        raise ValueError("args debe ser un objeto")
    limpio: dict = {}
    for clave, valor in args.items():
        if clave not in cap.args_schema:
            raise ValueError(f"argumento no permitido: {clave}")
        spec = cap.args_schema[clave]
        tipo = spec.get("tipo", "str")
        if tipo == "int":
            try:
                valor = int(valor)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{clave} debe ser entero") from exc
        elif tipo == "bool":
            valor = bool(valor) if isinstance(valor, bool) else str(valor).lower() in ("1", "true", "si", "sí")
        elif tipo == "dict":
            if not isinstance(valor, dict):
                raise ValueError(f"{clave} debe ser un objeto")
        elif tipo == "any":
            pass  # se normaliza en la propia capacidad (p.ej. filtros)
        else:
            valor = str(valor)
        enum = spec.get("enum")
        if enum and valor not in enum:
            raise ValueError(f"{clave} fuera de {enum}")
        limpio[clave] = valor
    for clave, spec in cap.args_schema.items():
        if spec.get("requerido") and clave not in limpio:
            raise ValueError(f"falta argumento requerido: {clave}")
    return limpio
