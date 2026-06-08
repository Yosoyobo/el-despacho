"""Registry de herramientas READ-ONLY del Chat del Taller (S-Chalan-Chat-V1).

El Chalán conversacional SOLO puede consultar datos a través de este whitelist
de funciones de solo lectura. Cada herramienta envuelve una pieza ya existente
del sistema (catálogo de KPIs, kpi_dsl vetado, modelos, stats de IA, lib.site)
y devuelve un dict pequeño y recortado.

Guardrails:
- Whitelist físico: `HERRAMIENTAS` dict. Una herramienta inexistente nunca se
  ejecuta — el caller devuelve `{"error": "herramienta_inexistente"}`.
- Whitelist de args: `validar_args` rechaza claves fuera del `args_schema`.
- Gating por rol: `herramientas_para(usuario)` filtra; además el caller
  re-chequea el gating antes de ejecutar (doble guardrail).
- Sin escritura: ninguna herramienta muta la DB.

Las acciones de ESCRITURA NO viven aquí — pasan por el flujo de Dictado
(`services.aplicar`) con preview/confirm humano.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

MAX_CHARS_TOOL = 1200
_TOP_N = 5


@dataclass(frozen=True)
class Herramienta:
    nombre: str
    descripcion: str
    # {arg: {"tipo": "str"|"int"|"bool", "requerido": bool, "enum": [...]?}}
    args_schema: dict[str, dict]
    # "abierto" | "finanzas" | "cartera" | "cotizaciones" | "facturacion"
    gating: str
    fn: Callable[[dict, Any], dict] = field(repr=False)


# ── Gating ──────────────────────────────────────────────────────────────────

def _gate_ok(gating: str, usuario) -> bool:
    if gating == "abierto":
        return True
    from lib import permisos
    fn = {
        "finanzas": permisos.puede_ver_finanzas,
        "cartera": permisos.puede_ver_cartera,
        "cotizaciones": permisos.puede_ver_cotizaciones,
        "facturacion": permisos.puede_ver_facturacion,
    }.get(gating)
    return bool(fn(usuario)) if fn else False


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


# ── Validación de args ────────────────────────────────────────────────────────

def validar_args(h: Herramienta, args: dict) -> dict:
    """Whitelist de claves + tipos + enums + requeridos. Lanza ValueError."""
    if not isinstance(args, dict):
        raise ValueError("args debe ser un objeto")
    limpio: dict = {}
    for clave, valor in args.items():
        if clave not in h.args_schema:
            raise ValueError(f"argumento no permitido: {clave}")
        spec = h.args_schema[clave]
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
        else:
            valor = str(valor)
        enum = spec.get("enum")
        if enum and valor not in enum:
            raise ValueError(f"{clave} fuera de {enum}")
        limpio[clave] = valor
    for clave, spec in h.args_schema.items():
        if spec.get("requerido") and clave not in limpio:
            raise ValueError(f"falta argumento requerido: {clave}")
    return limpio


# ── Implementaciones (todas read-only) ────────────────────────────────────────

def _rol(usuario) -> str:
    return getattr(usuario, "rol", "") or ""


def _h_listar_kpis(args: dict, usuario) -> dict:
    from apps.taller_home.kpis import kpis_aplicables_a_rol
    categoria = args.get("categoria")
    kpis = kpis_aplicables_a_rol(_rol(usuario), user=usuario)
    filas = [
        {"slug": k.slug, "titulo": k.titulo, "categoria": k.categoria}
        for k in kpis
        if not categoria or k.categoria == categoria
    ]
    return {"kpis": filas, "total": len(filas)}


def _h_consultar_kpi(args: dict, usuario) -> dict:
    from apps.taller_home.kpis import kpi_por_slug
    slug = args["slug"]
    kpi = kpi_por_slug(slug)
    if kpi is None:
        return {"error": "kpi_inexistente", "slug": slug}
    if _rol(usuario) not in kpi.roles_visible:
        return {"error": "sin_permiso", "slug": slug}
    res = kpi.calcular(usuario)
    return {"titulo": kpi.titulo, "valor": res.get("valor"),
            "nota": res.get("nota", ""), "link": res.get("link", "")}


# Entidades del DSL que tocan dinero — requieren permiso de finanzas.
_ENTIDADES_FINANZAS = {"egreso", "ingreso"}


def _h_consultar_metrica(args: dict, usuario) -> dict:
    from lib import permisos
    from lib.kpi_dsl.ejecutor import ejecutar_con_preview
    definicion = {
        "entidad": args.get("entidad"),
        "agregacion": args.get("agregacion", "count"),
    }
    for opt in ("campo", "ventana_tiempo", "alcance_usuario"):
        if args.get(opt):
            definicion[opt] = args[opt]
    if args.get("filtros"):
        definicion["filtros"] = args["filtros"]
    if definicion["entidad"] in _ENTIDADES_FINANZAS and not permisos.puede_ver_finanzas(usuario):
        return {"error": "sin_permiso"}
    salida = ejecutar_con_preview(definicion, usuario=usuario)
    if not salida.get("ok"):
        return {"error": salida.get("error", "consulta fuera de alcance")}
    return salida["resultado"]


def _h_detalle_proyecto(args: dict, usuario) -> dict:
    from apps.los_proyectos.models import Proyecto

    from lib import permisos
    slug = args["proyecto_slug"].strip().lstrip("#").lower()
    p = (
        Proyecto.objects.filter(slug=slug).first()
        or Proyecto.objects.filter(codigo__iexact=slug).first()
        or Proyecto.objects.filter(slug_legacy=slug).first()
    )
    if p is None:
        return {"error": "no_encontrado", "proyecto_slug": slug}
    if not permisos.puede_ver_proyecto(usuario, p):
        return {"error": "sin_permiso"}
    asignados = [
        {"usuario": a.usuario.get_full_name() or a.usuario.email, "rol": a.rol_en_proyecto}
        for a in p.asignaciones.select_related("usuario").all()
    ]
    return {
        "codigo": p.codigo,
        "nombre": p.nombre,
        "estado": p.get_estado_display(),
        "cliente": p.cliente.razon_social if p.cliente_id else None,
        "fecha_compromiso": p.fecha_compromiso.date().isoformat() if p.fecha_compromiso else None,
        "monto_cotizado": p.monto_cotizado,
        "asignados": asignados,
        "link": f"/proyectos/{p.slug}/",
    }


def _h_detalle_cliente(args: dict, usuario) -> dict:
    from apps.la_cartera.models import Cliente
    slug = args["cliente_slug"].strip().lstrip("$").lower()
    c = (
        Cliente.objects.filter(slug=slug).first()
        or Cliente.objects.filter(razon_social__icontains=slug).first()
    )
    if c is None:
        return {"error": "no_encontrado", "cliente_slug": slug}
    return {
        "razon_social": c.razon_social,
        "estado": c.get_estado_display(),
        "rfc": c.rfc or None,
        "contacto": c.nombre_contacto or None,
        "num_proyectos": c.proyectos.count(),
        "link": f"/clientes/{c.slug}/",
    }


def _h_detalle_factura(args: dict, usuario) -> dict:
    from apps.facturacion.models import Factura
    codigo = args["codigo"].strip().upper()
    f = Factura.objects.filter(codigo__iexact=codigo).first()
    if f is None:
        return {"error": "no_encontrado", "codigo": codigo}
    return {
        "codigo": f.codigo,
        "titulo": f.titulo,
        "cliente": f.cliente.razon_social if f.cliente_id else None,
        "estado": getattr(f, "estado_visible", f.get_estado_display()),
        "total": getattr(f, "total", None),
        "saldo_pendiente": getattr(f, "saldo_pendiente", None),
        "link": f"/facturacion/{f.pk}/",
    }


def _h_detalle_cotizacion(args: dict, usuario) -> dict:
    from apps.cotizaciones.models import Cotizacion
    codigo = args["codigo"].strip().upper()
    c = Cotizacion.objects.filter(codigo__iexact=codigo).first()
    if c is None:
        return {"error": "no_encontrado", "codigo": codigo}
    return {
        "codigo": c.codigo,
        "titulo": c.titulo,
        "cliente": c.cliente.razon_social if c.cliente_id else None,
        "estado": getattr(c, "estado_visible", c.get_estado_display()),
        "total": getattr(c, "total", None),
        "link": f"/cotizaciones/{c.pk}/",
    }


def _h_gasto_ia(args: dict, usuario) -> dict:
    from lib.analistas.stats import resumen_global
    dias = int(args.get("dias", 30))
    dias = max(1, min(dias, 365))
    r = resumen_global(dias=dias)
    return {
        "dias": dias,
        "costo_total_usd": r.get("costo_total"),
        "llamadas_total": r.get("llamadas_total"),
        "tokens_total": r.get("tokens_total"),
        "por_proveedor": [
            {"provider": p["provider"], "costo_usd": p["costo_usd"],
             "tokens": p["tokens"], "llamadas": p["llamadas"]}
            for p in r.get("por_proveedor", [])[:_TOP_N]
        ],
    }


def _h_estado_servidor(args: dict, usuario) -> dict:
    salida: dict = {}
    try:
        from lib.site.gauges import snapshot_gauges_minimo
        snap = snapshot_gauges_minimo()
        gauges = snap.get("gauges", {})
        salida["recursos"] = {
            nombre: {"pct": g.get("pct"), "estado": g.get("color")}
            for nombre, g in gauges.items()
        }
        cont = snap.get("containers", {})
        salida["containers"] = {
            "running": cont.get("running"), "total": cont.get("containers"),
        }
    except Exception:  # noqa: BLE001 — /proc no montado, etc.
        salida["recursos"] = {"disponible": False}
    if args.get("detallado"):
        try:
            from lib.site.registry import chequear_todas
            plataformas = chequear_todas()
            salida["integraciones"] = {
                k: v.get("estado") for k, v in plataformas.items()
            }
        except Exception:  # noqa: BLE001
            salida["integraciones"] = {"disponible": False}
    return salida


def _h_specs_servidor(args: dict, usuario) -> dict:
    salida: dict = {}
    try:
        from lib.site.host import snapshot
        snap = snapshot()
        mem = snap.get("memoria", {})
        disco = snap.get("disco", {})
        cpu = snap.get("cpu_load", {})
        salida = {
            "cpu_cores": cpu.get("cores"),
            "ram_total_mb": mem.get("total_mb"),
            "disco_total_gb": disco.get("total_gb"),
            "uptime": (snap.get("uptime") or {}).get("humano"),
        }
    except Exception:  # noqa: BLE001
        salida = {"disponible": False}
    try:
        from lib.site.droplet import info_local
        salida["host"] = info_local().get("nombre_logico")
    except Exception:  # noqa: BLE001
        pass
    return salida


# ── Registry ──────────────────────────────────────────────────────────────────

HERRAMIENTAS: dict[str, Herramienta] = {
    "listar_kpis": Herramienta(
        nombre="listar_kpis",
        descripcion="Lista los indicadores (KPIs) disponibles para el usuario. Arg opcional: categoria.",
        args_schema={"categoria": {"tipo": "str", "requerido": False}},
        gating="abierto", fn=_h_listar_kpis,
    ),
    "consultar_kpi": Herramienta(
        nombre="consultar_kpi",
        descripcion="Devuelve el valor actual de un KPI por su slug (usa listar_kpis para ver los slugs).",
        args_schema={"slug": {"tipo": "str", "requerido": True}},
        gating="abierto", fn=_h_consultar_kpi,
    ),
    "consultar_metrica": Herramienta(
        nombre="consultar_metrica",
        descripcion=(
            "Métrica agregada vía consulta acotada. entidad ∈ {proyecto, tarea, cliente, "
            "egreso, ingreso, recado, buzon_mensaje}; agregacion ∈ {count, sum, avg, min, max}; "
            "campo (para sum/avg/min/max); ventana_tiempo ∈ {siempre, ultimos_7d, ultimos_30d, "
            "este_mes, este_ano}; alcance_usuario ∈ {todos, mio}; filtros (objeto)."
        ),
        args_schema={
            "entidad": {"tipo": "str", "requerido": True},
            "agregacion": {"tipo": "str", "requerido": False,
                           "enum": ["count", "sum", "avg", "min", "max"]},
            "campo": {"tipo": "str", "requerido": False},
            "ventana_tiempo": {"tipo": "str", "requerido": False,
                               "enum": ["siempre", "ultimos_7d", "ultimos_30d", "este_mes", "este_ano"]},
            "alcance_usuario": {"tipo": "str", "requerido": False, "enum": ["todos", "mio"]},
            "filtros": {"tipo": "dict", "requerido": False},
        },
        gating="abierto", fn=_h_consultar_metrica,
    ),
    "detalle_proyecto": Herramienta(
        nombre="detalle_proyecto",
        descripcion="Estatus de un proyecto por código (LC-0001) o slug.",
        args_schema={"proyecto_slug": {"tipo": "str", "requerido": True}},
        gating="abierto", fn=_h_detalle_proyecto,
    ),
    "detalle_cliente": Herramienta(
        nombre="detalle_cliente",
        descripcion="Datos de un cliente por slug o razón social.",
        args_schema={"cliente_slug": {"tipo": "str", "requerido": True}},
        gating="cartera", fn=_h_detalle_cliente,
    ),
    "detalle_factura": Herramienta(
        nombre="detalle_factura",
        descripcion="Estatus de una factura por código (FAC-2026-0001).",
        args_schema={"codigo": {"tipo": "str", "requerido": True}},
        gating="facturacion", fn=_h_detalle_factura,
    ),
    "detalle_cotizacion": Herramienta(
        nombre="detalle_cotizacion",
        descripcion="Estatus de una cotización por código (COT-2026-0001).",
        args_schema={"codigo": {"tipo": "str", "requerido": True}},
        gating="cotizaciones", fn=_h_detalle_cotizacion,
    ),
    "gasto_ia": Herramienta(
        nombre="gasto_ia",
        descripcion="Gasto en IA (costo USD, llamadas, tokens) por proveedor. Arg opcional: dias (default 30).",
        args_schema={"dias": {"tipo": "int", "requerido": False}},
        gating="abierto", fn=_h_gasto_ia,
    ),
    "estado_servidor": Herramienta(
        nombre="estado_servidor",
        descripcion="Estado del servidor: CPU, memoria, disco, containers. Arg opcional: detallado (incluye integraciones).",
        args_schema={"detallado": {"tipo": "bool", "requerido": False}},
        gating="abierto", fn=_h_estado_servidor,
    ),
    "specs_servidor": Herramienta(
        nombre="specs_servidor",
        descripcion="Especificaciones del servidor: cores de CPU, RAM total, disco total, uptime.",
        args_schema={},
        gating="abierto", fn=_h_specs_servidor,
    ),
}


def herramientas_para(usuario) -> list[Herramienta]:
    """Herramientas visibles para el rol del usuario (filtra por gating)."""
    return [h for h in HERRAMIENTAS.values() if _gate_ok(h.gating, usuario)]


def ejecutar_herramienta(nombre: str, args: dict, usuario) -> dict:
    """Valida whitelist + gating + args, ejecuta y recorta. Nunca lanza."""
    h = HERRAMIENTAS.get(nombre)
    if h is None:
        return {"error": "herramienta_inexistente", "nombre": nombre}
    if not _gate_ok(h.gating, usuario):
        return {"error": "sin_permiso", "nombre": nombre}
    try:
        limpios = validar_args(h, args or {})
    except ValueError as exc:
        return {"error": "args_invalidos", "detalle": str(exc)}
    try:
        salida = h.fn(limpios, usuario)
    except Exception as exc:  # noqa: BLE001 — una herramienta nunca tumba el chat
        return {"error": "fallo_herramienta", "detalle": str(exc)[:200]}
    return recortar(salida)
