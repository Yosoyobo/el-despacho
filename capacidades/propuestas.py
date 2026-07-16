"""Capacidades de ESCRITURA como tools de PROPUESTA (S-Chalan-MCP-V1 commit 3).

Cada acción de escritura de El Dictado (`lib.dictado_catalogo.COMANDOS_DICTADO`)
se expone como una capacidad `modo="propuesta"` cuyo nombre es el `tipo` de la
acción (crear_tarea, registrar_egreso, crear_cliente, …). El Chalán la LLAMA
para PROPONER un cambio; el orquestador (`services_chat`) NO la ejecuta: bufferea
la propuesta y, al cerrar el turno, crea UN Dictado con todas para que el usuario
las revise y confirme (regla §20 — nunca se auto-aplican).

Que el nombre del tool sea el `tipo` garantiza que el tipo propuesto SIEMPRE es
válido (elimina de raíz el bug "propone pero no aplica" por tipo inexistente).

El gating reusa el mapa de escritura del catálogo (`_gating_checks`) vía
`capacidades.gating.gate_ok(..., modo="propuesta")` — misma política que
`comandos_para`, sin duplicarla.
"""

from __future__ import annotations

from lib.dictado_catalogo import COMANDOS_DICTADO

from .registro import MODO_PROPUESTA, Capacidad, registrar

TITULOS: dict[str, str] = {c["tipo"]: c.get("titulo", c["tipo"]) for c in COMANDOS_DICTADO}


def titulo_de(tipo: str) -> str:
    return TITULOS.get(tipo, tipo)


def _noop(args: dict, usuario) -> dict:
    """No se ejecuta desde el registro: las propuestas se bufferean en el
    orquestador y se materializan como Dictado. Existe por consistencia del
    contrato de `Capacidad` (y si algún día se sirven dinámicamente, devuelve el
    payload sin mutar nada)."""
    return {"propuesta": True, "payload": args}


def _capacidad(cmd: dict) -> Capacidad:
    payload = cmd.get("payload", "") or "(sin payload)"
    ejemplo = cmd.get("ejemplo", "")
    desc = f"{cmd['titulo']}. PROPONE este cambio (no se aplica; el usuario lo confirma)."
    if ejemplo:
        desc += f" Ejemplo: {ejemplo}"
    return Capacidad(
        nombre=cmd["tipo"],
        descripcion=desc,
        args_schema={},
        gating=cmd.get("gating", "abierto"),
        fn=_noop,
        modo=MODO_PROPUESTA,
        json_schema={
            "type": "object",
            "additionalProperties": True,
            "description": f"Campos de la acción: {payload}",
        },
    )


for _cmd in COMANDOS_DICTADO:
    registrar(_capacidad(_cmd))
