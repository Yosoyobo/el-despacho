"""Validador del DSL — falla rápido y con mensaje claro si el JSON sale del whitelist.

Normaliza a la forma que se guarda en `KPICustom.definicion_json`. Las seis
llaves v1 van SIEMPRE; las v2 sólo cuando la definición las usa, así que una
definición v1 se normaliza exactamente como antes (candado:
`tests/test_kpi_dsl_v1_retro.py`).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from .schema import (
    _OPS_V1,
    AGREGACIONES,
    AGREGACIONES_DURACION,
    ALCANCES_USUARIO,
    DIRECCIONES,
    ENTIDADES,
    FORMATOS,
    MAX_DIAS_RELATIVOS,
    OPS_FILTRO,
    TIPOS_AGREGABLES,
    TIPOS_KPI,
    TOP_GRUPOS_DEFAULT,
    TOP_GRUPOS_MAX,
    VENTANAS_TIEMPO,
    ops_de,
)

MAX_FILTROS = 20
MAX_VALORES_IN = 200
_RE_RELATIVA = re.compile(r"^(hace|en)_(\d{1,4})_dias$")
_ESCALARES = (str, int, float, bool)


class ValidacionError(ValueError):
    """El DSL no cumple el schema. NUNCA se debe ejecutar un DSL no validado."""


# ── Valores de fecha ─────────────────────────────────────────────────────────


def es_fecha_valida(valor: Any) -> bool:
    """"hoy", "hace_N_dias", "en_N_dias" o una fecha ISO «AAAA-MM-DD»."""
    if not isinstance(valor, str):
        return False
    if valor == "hoy":
        return True
    m = _RE_RELATIVA.match(valor)
    if m:
        return int(m.group(2)) <= MAX_DIAS_RELATIVOS
    try:
        date.fromisoformat(valor)
    except ValueError:
        return False
    return len(valor) == 10


def _como_bool(valor: Any, donde: str) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, int) and valor in (0, 1):
        return bool(valor)
    if isinstance(valor, str) and valor.strip().lower() in ("true", "false", "1", "0"):
        return valor.strip().lower() in ("true", "1")
    raise ValidacionError(f"{donde} espera verdadero o falso.")


def _como_numero(valor: Any, donde: str) -> int | float:
    if isinstance(valor, bool):
        raise ValidacionError(f"{donde} espera un número.")
    if isinstance(valor, int | float):
        return valor
    if isinstance(valor, str):
        try:
            return float(valor.strip())
        except ValueError:
            pass
    raise ValidacionError(f"{donde} espera un número.")


def _como_pk(valor: Any, donde: str) -> int:
    if isinstance(valor, bool):
        raise ValidacionError(f"{donde} espera el id de un registro.")
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    raise ValidacionError(f"{donde} espera el id de un registro.")


def _valor_escalar(tipo: str, valor: Any, donde: str) -> Any:
    """Un valor de `eq`/`gt`/… según el tipo del campo."""
    if tipo == "booleano":
        return _como_bool(valor, donde)
    if tipo in ("numero", "dinero"):
        return _como_numero(valor, donde)
    if tipo == "fecha":
        if not es_fecha_valida(valor):
            raise ValidacionError(
                f"{donde} espera una fecha AAAA-MM-DD, \"hoy\", \"hace_N_dias\" o \"en_N_dias\".",
            )
        return valor
    if tipo == "relacion":
        return _como_pk(valor, donde)
    # texto / opcion: v1 dejaba pasar cualquier escalar; se conserva.
    if not isinstance(valor, _ESCALARES) and valor is not None:
        raise ValidacionError(f"{donde} espera un texto.")
    return valor


# ── Filtros ──────────────────────────────────────────────────────────────────


def _validar_filtros(entidad: str, filtros_raw: Any, *, nombre: str = "filtros") -> list[dict]:
    cfg = ENTIDADES[entidad]
    if filtros_raw is None:
        filtros_raw = []
    if not isinstance(filtros_raw, list):
        raise ValidacionError(f"`{nombre}` debe ser una lista.")
    if len(filtros_raw) > MAX_FILTROS:
        raise ValidacionError(f"`{nombre}` admite a lo más {MAX_FILTROS} filtros.")
    filtros: list[dict] = []
    for f in filtros_raw:
        if not isinstance(f, dict):
            raise ValidacionError("Cada filtro debe ser un objeto.")
        f_campo = f.get("campo")
        f_op = f.get("op", "eq")
        if not isinstance(f_campo, str) or f_campo not in cfg["campos"]:
            raise ValidacionError(
                f"Campo de filtro '{f_campo}' no permitido en `{entidad}`. "
                f"Permitidos: {', '.join(cfg['campos']) or '<ninguno>'}.",
            )
        if f_op not in OPS_FILTRO:
            raise ValidacionError(f"Op '{f_op}' no permitida. Opciones: {', '.join(OPS_FILTRO)}.")
        if f_op not in ops_de(entidad, f_campo):
            raise ValidacionError(
                f"Op '{f_op}' no aplica al campo '{f_campo}' en `{entidad}`.",
            )
        tipo = cfg["campos"][f_campo]["tipo"]
        donde = f"El filtro '{f_campo} {f_op}'"

        # Comparar contra OTRO campo de la entidad (p. ej. completada_en ≤ fecha_compromiso).
        if "campo_ref" in f:
            ref = f["campo_ref"]
            if f_op not in ("eq", "gt", "gte", "lt", "lte"):
                raise ValidacionError(f"{donde} no puede compararse contra otro campo.")
            if not isinstance(ref, str) or ref not in cfg["campos"]:
                raise ValidacionError(f"`campo_ref` '{ref}' no permitido en `{entidad}`.")
            tipo_ref = cfg["campos"][ref]["tipo"]
            familia = {"numero": "num", "dinero": "num", "fecha": "fecha"}
            if familia.get(tipo) is None or familia.get(tipo) != familia.get(tipo_ref):
                raise ValidacionError(
                    f"{donde} sólo compara fechas con fechas y números con números.",
                )
            filtros.append({"campo": f_campo, "op": f_op, "campo_ref": ref})
            continue

        f_valor = f.get("valor")
        if f_op in _OPS_V1.get(entidad, {}).get(f_campo, ()):
            # Filtro que ya existía en v1: su valor pasa como pasaba entonces
            # (sin revisar tipo), para que ninguna definición guardada deje de
            # validar. El ORM hace la misma coerción que hacía.
            if f_op == "in" and not isinstance(f_valor, list):
                raise ValidacionError("Op 'in' requiere `valor` como lista.")
            filtros.append({"campo": f_campo, "op": f_op, "valor": f_valor})
            continue
        if f_op == "vacio":
            f_valor = _como_bool(True if f_valor is None else f_valor, donde)
        elif f_op == "in":
            if not isinstance(f_valor, list):
                raise ValidacionError("Op 'in' requiere `valor` como lista.")
            # Una lista vacía no casa con nada (v1 la aceptaba: se conserva).
            if len(f_valor) > MAX_VALORES_IN:
                raise ValidacionError(f"Op 'in' admite a lo más {MAX_VALORES_IN} valores.")
            f_valor = [_valor_escalar(tipo, v, donde) for v in f_valor]
        else:
            f_valor = _valor_escalar(tipo, f_valor, donde)
        filtros.append({"campo": f_campo, "op": f_op, "valor": f_valor})
    return filtros


# ── Validación completa ──────────────────────────────────────────────────────


def validar(definicion: Any) -> dict:
    """Valida y normaliza una definición DSL. Levanta ValidacionError si falla.

    Retorna el dict normalizado (con defaults aplicados), listo para ejecutar.
    """
    if not isinstance(definicion, dict):
        raise ValidacionError("La definición debe ser un objeto JSON.")

    entidad = definicion.get("entidad")
    if not isinstance(entidad, str) or entidad not in ENTIDADES:
        raise ValidacionError(
            f"Entidad '{entidad}' no permitida. Opciones: {', '.join(ENTIDADES)}.",
        )
    cfg = ENTIDADES[entidad]
    extra: dict[str, Any] = {}

    agregacion = definicion.get("agregacion", "count")
    if agregacion not in AGREGACIONES:
        raise ValidacionError(
            f"Agregación '{agregacion}' no permitida. Opciones: {', '.join(AGREGACIONES)}.",
        )

    campo = definicion.get("campo")
    duracion = definicion.get("duracion")
    if duracion is not None:
        if duracion not in cfg["duraciones"]:
            raise ValidacionError(
                f"Duración '{duracion}' no permitida en `{entidad}`. "
                f"Permitidas: {', '.join(cfg['duraciones']) or '<ninguna>'}.",
            )
        if agregacion not in AGREGACIONES_DURACION:
            raise ValidacionError(
                f"Una duración se agrega con {', '.join(AGREGACIONES_DURACION)}, no con '{agregacion}'.",
            )
        if campo:
            raise ValidacionError("Usa `campo` o `duracion`, no los dos.")
        extra["duracion"] = duracion
    elif agregacion != "count":
        if not campo:
            raise ValidacionError(f"La agregación '{agregacion}' requiere `campo`.")
        if campo not in cfg["campos"] or cfg["campos"][campo]["tipo"] not in TIPOS_AGREGABLES:
            raise ValidacionError(
                f"El campo '{campo}' no es agregable en `{entidad}`. "
                f"Permitidos: {', '.join(cfg['campos_numericos']) or '<ninguno>'}.",
            )

    filtros = _validar_filtros(entidad, definicion.get("filtros"))

    ventana = definicion.get("ventana_tiempo", "siempre")
    if ventana not in VENTANAS_TIEMPO:
        raise ValidacionError(
            f"Ventana '{ventana}' no permitida. Opciones: {', '.join(VENTANAS_TIEMPO)}.",
        )

    campo_fecha = definicion.get("campo_fecha")
    if campo_fecha is not None and campo_fecha != cfg["campo_fecha"]:
        spec = cfg["campos"].get(campo_fecha) if isinstance(campo_fecha, str) else None
        if spec is None or spec["tipo"] != "fecha":
            fechas = [c for c, s in cfg["campos"].items() if s["tipo"] == "fecha"]
            raise ValidacionError(
                f"`campo_fecha` '{campo_fecha}' no es una fecha de `{entidad}`. "
                f"Opciones: {', '.join(fechas)}.",
            )
        extra["campo_fecha"] = campo_fecha

    alcance_usuario = definicion.get("alcance_usuario", "todos")
    if alcance_usuario not in ALCANCES_USUARIO:
        raise ValidacionError(
            f"`alcance_usuario` debe ser uno de {', '.join(ALCANCES_USUARIO)}.",
        )
    if alcance_usuario == "mio" and not (cfg["campo_autor"] or cfg["campo_asignado"]):
        raise ValidacionError(
            f"La entidad '{entidad}' no soporta `alcance_usuario='mio'`.",
        )

    tipo = definicion.get("tipo", "valor")
    if tipo not in TIPOS_KPI:
        raise ValidacionError(f"`tipo` debe ser uno de {', '.join(TIPOS_KPI)}.")
    if tipo == "porcentaje":
        numerador = _validar_filtros(
            entidad, definicion.get("filtros_numerador"), nombre="filtros_numerador",
        )
        if not numerador:
            raise ValidacionError(
                "Un porcentaje necesita `filtros_numerador`: qué parte del total se cuenta.",
            )
        extra["tipo"] = "porcentaje"
        extra["filtros_numerador"] = numerador
    elif definicion.get("filtros_numerador"):
        raise ValidacionError("`filtros_numerador` sólo aplica con `tipo: \"porcentaje\"`.")

    agrupar_por = definicion.get("agrupar_por")
    if agrupar_por is not None:
        if not isinstance(agrupar_por, str) or agrupar_por not in cfg["agrupaciones"]:
            raise ValidacionError(
                f"No se puede agrupar `{entidad}` por '{agrupar_por}'. "
                f"Opciones: {', '.join(cfg['agrupaciones']) or '<ninguna>'}.",
            )
        extra["agrupar_por"] = agrupar_por
        top = definicion.get("top", TOP_GRUPOS_DEFAULT)
        if isinstance(top, bool) or not isinstance(top, int) or not 1 <= top <= TOP_GRUPOS_MAX:
            raise ValidacionError(f"`top` debe ser un entero entre 1 y {TOP_GRUPOS_MAX}.")
        if top != TOP_GRUPOS_DEFAULT:
            extra["top"] = top
    elif "top" in definicion and definicion["top"] is not None:
        raise ValidacionError("`top` sólo aplica con `agrupar_por`.")

    comparar = definicion.get("comparar", False)
    if not isinstance(comparar, bool):
        raise ValidacionError("`comparar` debe ser verdadero o falso.")
    if comparar:
        if ventana == "siempre":
            raise ValidacionError(
                "Para comparar con el periodo anterior elige una ventana de tiempo (no «siempre»).",
            )
        extra["comparar"] = True

    formato = definicion.get("formato")
    if formato is not None:
        if formato not in FORMATOS:
            raise ValidacionError(f"`formato` debe ser uno de {', '.join(FORMATOS)}.")
        extra["formato"] = formato
    direccion = definicion.get("direccion")
    if direccion is not None:
        if direccion not in DIRECCIONES:
            raise ValidacionError(f"`direccion` debe ser una de {', '.join(DIRECCIONES)}.")
        extra["direccion"] = direccion

    return {
        "entidad": entidad,
        "agregacion": agregacion,
        "campo": campo if (agregacion != "count" and duracion is None) else None,
        "filtros": filtros,
        "ventana_tiempo": ventana,
        "alcance_usuario": alcance_usuario,
        **extra,
    }


# ── Lo que se deriva de una definición válida ───────────────────────────────


def campos_usados(normalizada: dict) -> list[str]:
    """Todas las llaves-campo que toca la definición (para permisos)."""
    cfg = ENTIDADES[normalizada["entidad"]]
    usados: list[str] = []
    if normalizada.get("campo"):
        usados.append(normalizada["campo"])
    for f in [*normalizada["filtros"], *normalizada.get("filtros_numerador", [])]:
        usados.append(f["campo"])
        if f.get("campo_ref"):
            usados.append(f["campo_ref"])
    if normalizada.get("campo_fecha"):
        usados.append(normalizada["campo_fecha"])
    if normalizada.get("duracion"):
        d = cfg["duraciones"][normalizada["duracion"]]
        usados += [d["desde"], d["hasta"]]
    return usados


def permisos_de(definicion: Any) -> tuple[str, ...]:
    """Los permisos granulares («modulo.accion», hacen falta TODOS) para ver el
    dato de la definición: el de la entidad (el de «mío» si el alcance es
    «mio») más el de cada campo sensible que toque. super_admin siempre pasa.
    Valida primero: una definición inválida levanta ValidacionError."""
    n = validar(definicion)
    cfg = ENTIDADES[n["entidad"]]
    base = cfg["permiso_mio"] if n["alcance_usuario"] == "mio" else cfg["permiso"]
    salida: list[str] = list(base)
    for c in campos_usados(n):
        for p in cfg["campos"][c].get("permiso", ()):
            if p not in salida:
                salida.append(p)
    return tuple(dict.fromkeys(salida))


def metadatos_de(normalizada: dict) -> dict:
    """`formato` y `direccion` de una definición normalizada: los que trae, o
    los defaults (porcentaje → pct; duración → su unidad; dinero → dinero)."""
    cfg = ENTIDADES[normalizada["entidad"]]
    formato = normalizada.get("formato")
    if formato is None:
        if normalizada.get("tipo") == "porcentaje":
            formato = "pct"
        elif normalizada.get("duracion"):
            formato = cfg["duraciones"][normalizada["duracion"]]["unidad"]
        elif normalizada.get("campo"):
            spec = cfg["campos"][normalizada["campo"]]
            formato = spec.get("formato") or ("dinero" if spec["tipo"] == "dinero" else "numero")
        else:
            formato = "numero"
    # El motor no sabe si más es mejor: sin decirlo, sólo informa.
    return {"formato": formato, "direccion": normalizada.get("direccion") or "neutro"}
