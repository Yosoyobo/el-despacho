"""Lo que el DSL le cuenta a las personas: el esquema para armar el formulario
del constructor de KPIs (La Gerencia), la frase en español de una definición y
el resumen que lee El Chalán. Todo sale de `schema.py`: agregar un campo ahí
lo agrega al formulario, a la frase y al prompt sin tocar nada más.
"""

from __future__ import annotations

from typing import Any

from .schema import (
    AGREGACIONES,
    AGREGACIONES_DURACION,
    ALCANCES_USUARIO,
    DIRECCIONES,
    ENTIDADES,
    ETIQUETAS_AGREGACIONES,
    ETIQUETAS_DIRECCIONES,
    ETIQUETAS_FORMATOS,
    ETIQUETAS_OPS,
    ETIQUETAS_OPS_FECHA,
    ETIQUETAS_VENTANAS,
    FORMATOS,
    OPS_FILTRO,
    TIPOS_AGREGABLES,
    TIPOS_KPI,
    TOP_GRUPOS_DEFAULT,
    TOP_GRUPOS_MAX,
    VALORES_FECHA_ESPECIALES,
    VENTANAS_TIEMPO,
    ops_de,
    ruta_de,
)
from .validador import validar

# ── Esquema para la UI ───────────────────────────────────────────────────────


def _opciones(entidad: str, campo: str, spec: dict) -> list[dict] | None:
    """Las opciones de un campo `opcion`: las `choices` del modelo o las filas
    de su catálogo (estados de proyecto/tarea, tipos del buzón…)."""
    if spec["tipo"] != "opcion":
        return None
    from django.apps import apps

    try:
        if spec.get("catalogo"):
            Catalogo = apps.get_model(spec["catalogo"])
            filas = Catalogo._default_manager.order_by("orden", "label").values_list("slug", "label")
            return [{"valor": v, "etiqueta": e} for v, e in filas]
        Modelo = apps.get_model(ENTIDADES[entidad]["modelo"])
        actual = Modelo
        campo_m = None
        for parte in ruta_de(entidad, campo).split("__"):
            campo_m = actual._meta.get_field(parte)
            if campo_m.is_relation and campo_m.related_model is not None:
                actual = campo_m.related_model
        return [{"valor": v, "etiqueta": str(e)} for v, e in (campo_m.flatchoices or ())]
    except Exception:  # noqa: BLE001 — sin tabla o sin app: el formulario pide texto libre
        return []


def _puede(usuario, permisos: tuple[str, ...]) -> bool:
    from .ejecutor import _puede_ver
    return _puede_ver(usuario, permisos)


def esquema_para_ui(usuario=None) -> dict:
    """Todo lo que el formulario necesita, serializable a JSON.

    Con `usuario`, sólo las entidades cuyo dato puede ver (entera, o sólo «lo
    mío» — `solo_mio: true`) y sin los campos cuyo permiso no tiene. Sin
    `usuario`, todo lo que el motor admite. Las entidades cuyo modelo no está
    instalado en esta app se omiten.
    """
    from .ejecutor import entidad_disponible

    entidades: list[dict] = []
    for clave, cfg in ENTIDADES.items():
        if not entidad_disponible(clave):
            continue
        solo_mio = False
        if usuario is not None and not _puede(usuario, cfg["permiso"]):
            soporta_mio = bool(cfg["campo_autor"] or cfg["campo_asignado"])
            if not (soporta_mio and _puede(usuario, cfg["permiso_mio"])):
                continue
            solo_mio = True
        campos = []
        for c, spec in cfg["campos"].items():
            if usuario is not None and not _puede(usuario, tuple(spec.get("permiso", ()))):
                continue
            agregable = spec["tipo"] in TIPOS_AGREGABLES
            campos.append({
                "clave": c,
                "etiqueta": spec["etiqueta"],
                "tipo": spec["tipo"],
                "ops": list(ops_de(clave, c)),
                "agregaciones": ["sum", "avg", "min", "max"] if agregable else [],
                "opciones": _opciones(clave, c, spec),
                "formato": spec.get("formato") or ("dinero" if spec["tipo"] == "dinero" else None),
                "permiso": list(spec.get("permiso", ())),
            })
        visibles = {c["clave"] for c in campos}
        entidades.append({
            "clave": clave,
            "etiqueta": cfg["etiqueta"],
            "etiqueta_singular": cfg["etiqueta_singular"],
            "genero": cfg["genero"],
            "permiso": list(cfg["permiso"]),
            "permiso_mio": list(cfg["permiso_mio"]),
            "soporta_mio": bool(cfg["campo_autor"] or cfg["campo_asignado"]),
            "solo_mio": solo_mio,
            "campo_fecha": cfg["campo_fecha"],
            "campos_fecha": [c["clave"] for c in campos if c["tipo"] == "fecha"],
            "link": cfg["link_default"],
            "campos": campos,
            "agrupaciones": [
                {"clave": g, "etiqueta": s["etiqueta"]} for g, s in cfg["agrupaciones"].items()
            ],
            "duraciones": [
                {"clave": d, "etiqueta": s["etiqueta"], "unidad": s["unidad"],
                 "agregaciones": list(AGREGACIONES_DURACION)}
                for d, s in cfg["duraciones"].items()
                if s["desde"] in visibles and s["hasta"] in visibles
            ],
        })
    return {
        "version": 2,
        "entidades": entidades,
        "agregaciones": [{"clave": a, "etiqueta": ETIQUETAS_AGREGACIONES[a]} for a in AGREGACIONES],
        "ops": [{"clave": o, "etiqueta": ETIQUETAS_OPS[o]} for o in OPS_FILTRO],
        "ops_fecha": [{"clave": o, "etiqueta": e} for o, e in ETIQUETAS_OPS_FECHA.items()],
        "valores_fecha_especiales": list(VALORES_FECHA_ESPECIALES),
        "ventanas": [
            {"clave": v, "etiqueta": ETIQUETAS_VENTANAS[v], "comparable": v != "siempre"}
            for v in VENTANAS_TIEMPO
        ],
        "alcances": [{"clave": "todos", "etiqueta": "Todo el despacho"},
                     {"clave": "mio", "etiqueta": "Sólo lo mío"}],
        "tipos": [{"clave": "valor", "etiqueta": "Un número"},
                  {"clave": "porcentaje", "etiqueta": "Un porcentaje (una parte del total)"}],
        "formatos": [{"clave": f, "etiqueta": ETIQUETAS_FORMATOS[f]} for f in FORMATOS],
        "direcciones": [{"clave": d, "etiqueta": ETIQUETAS_DIRECCIONES[d]} for d in DIRECCIONES],
        "top_default": TOP_GRUPOS_DEFAULT,
        "top_max": TOP_GRUPOS_MAX,
    }


# ── La frase ─────────────────────────────────────────────────────────────────


def _art(spec: dict) -> str:
    """«del» / «de la» según el género de la etiqueta."""
    return "de la" if spec.get("genero") == "f" else "del"


def _valor_legible(spec: dict, valor: Any) -> str:
    if spec["tipo"] == "booleano":
        return "sí" if valor else "no"
    if spec["tipo"] == "fecha" and isinstance(valor, str):
        if valor == "hoy":
            return "hoy"
        if valor.startswith("hace_"):
            return f"hace {valor[5:-5]} días"
        if valor.startswith("en_"):
            return f"dentro de {valor[3:-5]} días"
    if spec["tipo"] == "dinero" and isinstance(valor, int | float):
        return f"${valor:,.2f}".replace(".00", "")
    return f"«{valor}»"


def _frase_filtro(entidad: str, f: dict) -> str:
    campos = ENTIDADES[entidad]["campos"]
    spec = campos[f["campo"]]
    nombre = spec["etiqueta"]
    op = f["op"]
    if op == "vacio":
        return f"sin {nombre}" if f["valor"] else f"con {nombre}"
    if spec["tipo"] == "booleano" and op == "eq":
        return f"que sí son «{nombre}»" if f["valor"] else f"que no son «{nombre}»"
    etiquetas = ETIQUETAS_OPS_FECHA if spec["tipo"] == "fecha" else ETIQUETAS_OPS
    verbo = etiquetas.get(op, ETIQUETAS_OPS[op])
    if "campo_ref" in f:
        ref = campos[f["campo_ref"]]
        cuyo = "cuya" if spec.get("genero") == "f" else "cuyo"
        el = "la" if ref.get("genero") == "f" else "el"
        return f"{cuyo} {nombre} {verbo} {el} {ref['etiqueta']}"
    if op == "in":
        valor = ", ".join(_valor_legible(spec, v) for v in f["valor"])
    else:
        valor = _valor_legible(spec, f["valor"])
    return f"con {nombre} que {verbo} {valor}"


def _unir(frases: list[str]) -> str:
    if len(frases) <= 1:
        return "".join(frases)
    return ", ".join(frases[:-1]) + " y " + frases[-1]


def describir(definicion: Any) -> str:
    """Una frase en español llano de lo que mide la definición, p. ej.
    «Suma del monto de los ingresos de este mes, agrupado por cliente.»
    Valida primero: una definición inválida levanta ValidacionError."""
    n = validar(definicion)
    cfg = ENTIDADES[n["entidad"]]
    los = "las" if cfg["genero"] == "f" else "los"
    entidad = cfg["etiqueta"]
    agg = n["agregacion"]

    if n.get("duracion"):
        d = cfg["duraciones"][n["duracion"]]
        que = f"{ETIQUETAS_AGREGACIONES[agg].capitalize()} de {d['etiqueta']} de {los} {entidad}"
    elif agg == "count":
        que = f"Número de {entidad}"
    else:
        spec = cfg["campos"][n["campo"]]
        que = (f"{ETIQUETAS_AGREGACIONES[agg].capitalize()} {_art(spec)} {spec['etiqueta']} "
               f"de {los} {entidad}")

    contexto = []
    filtros = [_frase_filtro(n["entidad"], f) for f in n["filtros"]]
    if filtros:
        contexto.append(_unir(filtros))
    if n["ventana_tiempo"] != "siempre":
        ventana = ETIQUETAS_VENTANAS[n["ventana_tiempo"]]
        if n.get("campo_fecha"):
            ventana += f" (según la {cfg['campos'][n['campo_fecha']]['etiqueta']})"
        contexto.append(ventana)

    if n.get("tipo") == "porcentaje":
        numerador = _unir([_frase_filtro(n["entidad"], f) for f in n["filtros_numerador"]])
        todos = "todas las" if cfg["genero"] == "f" else "todos los"
        if agg == "count":
            frase = f"Porcentaje de {entidad} {numerador}, sobre {todos} {entidad}"
        else:
            frase = (f"Porcentaje de {que[0].lower() + que[1:]} que corresponde a {entidad} "
                     f"{numerador}, sobre el total")
        if contexto:
            frase += " " + " ".join(contexto)
    else:
        frase = " ".join([que, *contexto])
    if n["alcance_usuario"] == "mio":
        frase += ", sólo lo mío"
    if n.get("agrupar_por"):
        frase += f", agrupado por {cfg['agrupaciones'][n['agrupar_por']]['etiqueta']}"
    if n.get("comparar"):
        frase += ", comparado con el periodo anterior"
    return frase + "."


# ── Para El Chalán ───────────────────────────────────────────────────────────


def resumen_para_prompt() -> str:
    """El esquema v2 en texto compacto para el prompt que traduce una pregunta
    a una definición. Generado del schema: nunca se desincroniza."""
    lineas: list[str] = []
    for clave, cfg in ENTIDADES.items():
        campos = []
        for c, spec in cfg["campos"].items():
            opciones = _opciones(clave, c, spec) or []
            valores = f"[{'|'.join(str(o['valor']) for o in opciones)}]" if opciones else ""
            campos.append(f"{c}:{spec['tipo']}{valores}")
        mio = "sí" if (cfg["campo_autor"] or cfg["campo_asignado"]) else "no"
        lineas.append(
            f"- {clave} ({cfg['etiqueta']}; fecha de la ventana={cfg['campo_fecha']}; mio={mio})\n"
            f"    campos: {', '.join(campos)}\n"
            f"    agrupar_por: {', '.join(cfg['agrupaciones']) or '<ninguno>'}\n"
            f"    duraciones: {', '.join(cfg['duraciones']) or '<ninguna>'}"
        )
    ops = "; ".join(f"{t}: {', '.join(o)}" for t, o in _ops_por_tipo().items())
    return (
        "ENTIDADES (campo:tipo[valores posibles]):\n" + "\n".join(lineas) + "\n\n"
        f"OPERADORES POR TIPO: {ops}\n"
        f"AGREGACIONES: {', '.join(AGREGACIONES)} (sum/avg/min/max sólo sobre campos numero/dinero; "
        f"sobre una duración: {', '.join(AGREGACIONES_DURACION)})\n"
        f"VENTANAS DE TIEMPO: {', '.join(VENTANAS_TIEMPO)}\n"
        f"ALCANCE DE USUARIO: {' | '.join(ALCANCES_USUARIO)} (mio filtra por autor/asignado)\n"
        f"TIPOS: {', '.join(TIPOS_KPI)} · FORMATOS: {', '.join(FORMATOS)} · "
        f"DIRECCIONES: {', '.join(DIRECCIONES)}\n"
        "FECHAS en filtros: \"AAAA-MM-DD\", \"hoy\", \"hace_N_dias\", \"en_N_dias\".\n"
    )


def _ops_por_tipo() -> dict[str, tuple[str, ...]]:
    from .schema import OPS_POR_TIPO
    return OPS_POR_TIPO
