"""Validador del DSL — falla rápido y con mensaje claro si el JSON sale del whitelist."""

from __future__ import annotations

from typing import Any

from .schema import (
    AGREGACIONES,
    ALCANCES_USUARIO,
    ENTIDADES,
    OPS_FILTRO,
    VENTANAS_TIEMPO,
)


class ValidacionError(ValueError):
    """El DSL no cumple el schema. NUNCA se debe ejecutar un DSL no validado."""


def validar(definicion: Any) -> dict:
    """Valida y normaliza una definición DSL. Levanta ValidacionError si falla.

    Retorna el dict normalizado (con defaults aplicados), listo para ejecutar.
    """
    if not isinstance(definicion, dict):
        raise ValidacionError("La definición debe ser un objeto JSON.")

    entidad = definicion.get("entidad")
    if entidad not in ENTIDADES:
        raise ValidacionError(
            f"Entidad '{entidad}' no permitida. Opciones: {', '.join(ENTIDADES)}.",
        )
    cfg = ENTIDADES[entidad]

    agregacion = definicion.get("agregacion", "count")
    if agregacion not in AGREGACIONES:
        raise ValidacionError(
            f"Agregación '{agregacion}' no permitida. Opciones: {', '.join(AGREGACIONES)}.",
        )

    campo = definicion.get("campo")
    if agregacion != "count":
        if not campo:
            raise ValidacionError(f"La agregación '{agregacion}' requiere `campo`.")
        if campo not in cfg["campos_numericos"]:
            raise ValidacionError(
                f"El campo '{campo}' no es agregable en `{entidad}`. "
                f"Permitidos: {', '.join(cfg['campos_numericos']) or '<ninguno>'}.",
            )

    filtros_raw = definicion.get("filtros") or []
    if not isinstance(filtros_raw, list):
        raise ValidacionError("`filtros` debe ser una lista.")
    filtros: list[dict] = []
    for f in filtros_raw:
        if not isinstance(f, dict):
            raise ValidacionError("Cada filtro debe ser un objeto.")
        f_campo = f.get("campo")
        f_op = f.get("op", "eq")
        f_valor = f.get("valor")
        if f_campo not in cfg["campos_filtrables"]:
            raise ValidacionError(
                f"Campo de filtro '{f_campo}' no permitido en `{entidad}`. "
                f"Permitidos: {', '.join(cfg['campos_filtrables']) or '<ninguno>'}.",
            )
        if f_op not in OPS_FILTRO:
            raise ValidacionError(f"Op '{f_op}' no permitida. Opciones: {', '.join(OPS_FILTRO)}.")
        if f_op not in cfg["campos_filtrables"][f_campo]:
            raise ValidacionError(
                f"Op '{f_op}' no aplica al campo '{f_campo}' en `{entidad}`.",
            )
        if f_op == "in" and not isinstance(f_valor, list):
            raise ValidacionError("Op 'in' requiere `valor` como lista.")
        filtros.append({"campo": f_campo, "op": f_op, "valor": f_valor})

    ventana = definicion.get("ventana_tiempo", "siempre")
    if ventana not in VENTANAS_TIEMPO:
        raise ValidacionError(
            f"Ventana '{ventana}' no permitida. Opciones: {', '.join(VENTANAS_TIEMPO)}.",
        )

    alcance_usuario = definicion.get("alcance_usuario", "todos")
    if alcance_usuario not in ALCANCES_USUARIO:
        raise ValidacionError(
            f"`alcance_usuario` debe ser uno de {', '.join(ALCANCES_USUARIO)}.",
        )
    if alcance_usuario == "mio" and not (cfg["campo_autor"] or cfg["campo_asignado"]):
        raise ValidacionError(
            f"La entidad '{entidad}' no soporta `alcance_usuario='mio'`.",
        )

    return {
        "entidad": entidad,
        "agregacion": agregacion,
        "campo": campo if agregacion != "count" else None,
        "filtros": filtros,
        "ventana_tiempo": ventana,
        "alcance_usuario": alcance_usuario,
    }
