"""Capacidades de LECTURA del Chalán (S-Chalan-MCP-V1).

Registradas en el registro único `capacidades` (antes vivían en
`el_dictado.herramientas`, hoy shim de compatibilidad). Cada una envuelve una
pieza ya existente del sistema (catálogo de KPIs, kpi_dsl vetado, modelos, stats
de IA, lib.site) y devuelve un dict pequeño y recortado. Todas son read-only:
ninguna muta la DB (las escrituras son `modo="propuesta"` y viven en
`propuestas.py`). Los guardrails (whitelist de nombres/args, recorte, gating)
viven en `capacidades.registro` y `capacidades.gating`.
"""

from __future__ import annotations

from .registro import _TOP_N, Capacidad, registrar

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


def _normalizar_filtros(filtros) -> list[dict]:
    """Acepta filtros como lista DSL `[{campo,op,valor}]` o como dict cómodo
    (`{campo: valor}` ó `{campo: {op, valor}}`) y devuelve siempre la lista DSL.

    Esto reconcilia lo que el LLM produce naturalmente (un objeto) con lo que
    el validador del DSL espera (una lista). Antes, cualquier filtro reventaba
    porque la herramienta forzaba dict y el DSL pedía lista.
    """
    if not filtros:
        return []
    if isinstance(filtros, list):
        return [f for f in filtros if isinstance(f, dict)]
    if isinstance(filtros, dict):
        out: list[dict] = []
        for campo, v in filtros.items():
            if isinstance(v, dict) and "valor" in v:
                out.append({"campo": campo, "op": v.get("op", "eq"), "valor": v["valor"]})
            else:
                out.append({"campo": campo, "op": "eq", "valor": v})
        return out
    return []


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
    filtros = _normalizar_filtros(args.get("filtros"))
    if filtros:
        definicion["filtros"] = filtros
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
    # Gastos del proyecto: costos derivados de los productos + Egresos reales
    # ya registrados en Tesorería (B 2026-06-07). Así el Chalán reporta cuánto
    # se ha gastado/se le adeuda a proveedores por este proyecto.
    from django.db.models import Count, Sum
    eg = p.egresos.filter(anulado=False).aggregate(n=Count("id"), total=Sum("monto"))
    deuda = [
        {"proveedor": d["proveedor"].razon_social, "total": float(d["total"])}
        for d in p.deuda_por_proveedor()
    ]
    return {
        "codigo": p.codigo,
        "nombre": p.nombre,
        "estado": p.get_estado_display(),
        "cliente": p.cliente.razon_social if p.cliente_id else None,
        "fecha_compromiso": p.fecha_compromiso.date().isoformat() if p.fecha_compromiso else None,
        "monto_cotizado": p.monto_cotizado,
        "asignados": asignados,
        "costo_produccion": float(p.costo_produccion),
        "utilidad_estimada": float(p.utilidad_productos),
        "egresos_registrados": {
            "cantidad": eg["n"] or 0,
            "total": float(eg["total"] or 0),
        },
        "deuda_por_proveedor": deuda,
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


def _h_resumen_finanzas(args: dict, usuario) -> dict:
    from apps.taller_home.negocio import hechos_finanzas
    h = hechos_finanzas()
    return {"dominio": "finanzas", "titulo": h["titulo"], "resumen": h["hechos"] or "Sin datos."}


def _h_resumen_cobranza(args: dict, usuario) -> dict:
    from apps.taller_home.negocio import hechos_cobranza
    h = hechos_cobranza()
    return {"dominio": "cobranza", "titulo": h["titulo"], "resumen": h["hechos"] or "Sin datos."}


def _h_resumen_ventas(args: dict, usuario) -> dict:
    from apps.taller_home.negocio import hechos_ventas
    h = hechos_ventas()
    return {"dominio": "ventas", "titulo": h["titulo"], "resumen": h["hechos"] or "Sin datos."}


def _h_resumen_margenes(args: dict, usuario) -> dict:
    from apps.taller_home.negocio import hechos_margenes
    h = hechos_margenes()
    return {"dominio": "margenes", "titulo": h["titulo"], "resumen": h["hechos"] or "Sin datos."}


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


def _h_detalle_ingreso(args: dict, usuario) -> dict:
    from apps.tesoreria.models import Ingreso
    codigo = args["codigo"].strip().upper()
    ing = Ingreso.objects.filter(codigo__iexact=codigo).first()
    if ing is None:
        return {"error": "no_encontrado", "codigo": codigo}
    return {
        "codigo": ing.codigo,
        "fecha": ing.fecha.isoformat() if ing.fecha else None,
        "monto": ing.monto,
        "descripcion": ing.descripcion,
        "cliente": ing.cliente.razon_social if ing.cliente_id else None,
        "proyecto": ing.proyecto.codigo if ing.proyecto_id else None,
        "metodo": ing.get_metodo_display(),
        "factura": ing.factura.codigo if ing.factura_id else None,
        "anulado": ing.anulado,
        "link": f"/tesoreria/ingresos/{ing.pk}/",
    }


def _h_detalle_tarea(args: dict, usuario) -> dict:
    from apps.el_pizarron.models.tarea import Tarea

    from lib import permisos
    t = Tarea.objects.filter(pk=args["tarea_id"]).select_related("proyecto", "asignada_a").first()
    if t is None:
        return {"error": "no_encontrado", "tarea_id": args["tarea_id"]}
    if not permisos.puede_ver_tarea(usuario, t):
        return {"error": "sin_permiso"}
    return {
        "id": t.pk,
        "titulo": t.titulo,
        "estado": t.get_estado_display(),
        "prioridad": t.get_prioridad_display(),
        "proyecto": t.proyecto.codigo,
        "asignada_a": (t.asignada_a.get_full_name() or t.asignada_a.email) if t.asignada_a_id else None,
        "fecha_compromiso": t.fecha_compromiso.isoformat() if t.fecha_compromiso else None,
        "link": f"/tareas/{t.pk}/",
    }


def _fila_tarea(t) -> dict:
    return {
        "id": t.pk, "titulo": t.titulo, "estado": t.get_estado_display(),
        "prioridad": t.get_prioridad_display(), "proyecto": t.proyecto.codigo,
        "fecha_compromiso": t.fecha_compromiso.isoformat() if t.fecha_compromiso else None,
        "link": f"/tareas/{t.pk}/",
    }


def _h_mis_tareas(args: dict, usuario) -> dict:
    from apps.el_pizarron.models.tarea import Tarea
    from django.db.models import Q
    # S-LC-Proyecto-V2: incluye las entregas/recogidas donde soy el runner.
    qs = (
        Tarea.objects.filter(Q(asignada_a=usuario) | Q(runner=usuario))
        .exclude(estado="completada")
        .select_related("proyecto")
        .order_by("fecha_compromiso", "-prioridad")
        .distinct()
    )
    filas = [_fila_tarea(t) for t in qs[:_TOP_N * 2]]
    return {"tareas": filas, "total": qs.count()}


def _h_mi_jornada_hoy(args: dict, usuario) -> dict:
    """Mi jornada de hoy: entrada/salida/retardo + si tengo cronómetro activo."""
    from apps.checador.models.jornada import Jornada
    from apps.checador.models.sesion import SesionProyecto

    from lib.fecha import ahora_mx
    hoy = ahora_mx().date()
    j = Jornada.objects.filter(usuario=usuario, fecha=hoy).first()
    timer = (
        SesionProyecto.objects.filter(usuario=usuario, estado="activa")
        .select_related("proyecto").first()
    )
    return {
        "fecha": str(hoy),
        "entrada": j.entrada_en.isoformat() if j and j.entrada_en else None,
        "salida": j.salida_en.isoformat() if j and j.salida_en else None,
        "retardo_min": (j.retardo_min if j else 0),
        "estado": (j.estado if j else "sin_checar"),
        "cronometro_activo": (
            {"proyecto": timer.proyecto.codigo} if timer else None
        ),
    }


def _h_mis_horas_semana(args: dict, usuario) -> dict:
    """Mis horas trabajadas, retardos y visitas de los últimos 7 días."""
    from datetime import timedelta

    from apps.checador import services

    from lib.fecha import ahora_mx
    hoy = ahora_mx().date()
    datos = services.horas_de(usuario, hoy - timedelta(days=6), hoy)
    return {"periodo": "últimos 7 días", **datos}


def _h_tareas_de_proyecto(args: dict, usuario) -> dict:
    from apps.el_pizarron.models.tarea import Tarea
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
    solo_abiertas = args.get("solo_abiertas", True)
    qs = Tarea.objects.filter(proyecto=p).select_related("proyecto").order_by("estado", "-prioridad")
    if solo_abiertas:
        qs = qs.exclude(estado="completada")
    filas = [_fila_tarea(t) for t in qs[:_TOP_N * 2]]
    return {"proyecto": p.codigo, "tareas": filas, "total": qs.count()}


def _h_contaduria_saldo_cuenta(args: dict, usuario) -> dict:
    from apps.contaduria.models import CuentaContable
    from apps.contaduria.services import saldo_cuenta
    clave = args["cuenta"].strip()
    cta = (
        CuentaContable.objects.filter(codigo__iexact=clave).first()
        or CuentaContable.objects.filter(slot=clave.lower()).first()
        or CuentaContable.objects.filter(nombre__icontains=clave).first()
    )
    if cta is None:
        return {"error": "no_encontrado", "cuenta": clave}
    return {
        "codigo": cta.codigo,
        "nombre": cta.nombre,
        "tipo": cta.get_tipo_display(),
        "saldo": saldo_cuenta(cta),
    }


def _h_contaduria_balance(args: dict, usuario) -> dict:
    from apps.contaduria.services import balance_de_comprobacion
    filas = balance_de_comprobacion()
    salida = [
        {"codigo": f["cuenta"].codigo, "nombre": f["cuenta"].nombre, "saldo": f["saldo"]}
        for f in filas
        if f["saldo"]
    ]
    return {"cuentas": salida[: _TOP_N * 3], "total_cuentas": len(salida)}


def _h_proximos_eventos(args: dict, usuario) -> dict:
    from datetime import date, timedelta

    from apps.calendario.services import eventos_por_dia
    dias = int(args.get("dias", 14))
    dias = max(1, min(dias, 90))
    hoy = date.today()
    por_dia = eventos_por_dia(usuario, hoy, hoy + timedelta(days=dias))
    salida: list[dict] = []
    for fecha in sorted(por_dia):
        for ev in por_dia[fecha]:
            salida.append({
                "fecha": fecha.isoformat(), "tipo": ev.get("tipo"),
                "titulo": ev.get("titulo"), "subtitulo": ev.get("subtitulo"),
            })
    return {"dias": dias, "eventos": salida[: _TOP_N * 3], "total": len(salida)}


def _h_buscar(args: dict, usuario) -> dict:
    """Búsqueda libre acotada por texto. Respeta el gating de cada entidad:
    proyectos (visibilidad por proyecto), clientes (cartera), facturas
    (facturación), cotizaciones (cotizaciones). Top-N por tipo."""
    from lib import permisos
    texto = args["texto"].strip()
    if len(texto) < 2:
        return {"error": "texto_muy_corto"}
    out: dict = {}

    from apps.los_proyectos.models import Proyecto
    proys = Proyecto.objects.filter(nombre__icontains=texto)[: _TOP_N * 2]
    out["proyectos"] = [
        {"codigo": p.codigo, "nombre": p.nombre, "estado": p.get_estado_display(),
         "link": f"/proyectos/{p.slug}/"}
        for p in proys if permisos.puede_ver_proyecto(usuario, p)
    ]

    if permisos.puede_ver_cartera(usuario):
        from apps.la_cartera.models import Cliente
        out["clientes"] = [
            {"razon_social": c.razon_social, "rfc": c.rfc or None, "link": f"/clientes/{c.slug}/"}
            for c in Cliente.objects.filter(razon_social__icontains=texto)[:_TOP_N]
        ]
    if permisos.puede_ver_facturacion(usuario):
        from apps.facturacion.models import Factura
        out["facturas"] = [
            {"codigo": f.codigo, "titulo": f.titulo, "link": f"/facturacion/{f.pk}/"}
            for f in Factura.objects.filter(titulo__icontains=texto)[:_TOP_N]
        ]
    if permisos.puede_ver_cotizaciones(usuario):
        from apps.cotizaciones.models import Cotizacion
        out["cotizaciones"] = [
            {"codigo": c.codigo, "titulo": c.titulo, "link": f"/cotizaciones/{c.pk}/"}
            for c in Cotizacion.objects.filter(titulo__icontains=texto)[:_TOP_N]
        ]
    return out


def _h_buscar_catalogo(args: dict, usuario) -> dict:
    """LC #153: busca productos (Servicio) y proveedores del Catálogo por nombre.
    Read-only. Devuelve precio/costo/margen + quién surte cada producto."""
    texto = args["texto"].strip()
    if len(texto) < 2:
        return {"error": "texto_muy_corto"}
    from apps.el_catalogo.models import Proveedor, Servicio
    productos = []
    for s in (
        Servicio.activos.filter(nombre__icontains=texto)
        .select_related("categoria").prefetch_related("proveedores")[:_TOP_N]
    ):
        productos.append({
            "nombre": s.nombre,
            "categoria": s.categoria.nombre if s.categoria_id else None,
            "precio": float(s.precio_base or 0),
            "costo": float(s.costo or 0),
            "margen_pct": round(s.margen_porcentaje, 1),
            "proveedores": [p.razon_social for p in s.proveedores.all() if p.activo][:5],
        })
    proveedores = [
        {"razon_social": p.razon_social, "contacto": p.nombre_contacto or None,
         "surte": [srv.nombre for srv in p.servicios.all() if srv.activo][:5]}
        for p in (
            Proveedor.objects.filter(activo=True, razon_social__icontains=texto)
            .prefetch_related("servicios")[:_TOP_N]
        )
    ]
    return {"productos": productos, "proveedores": proveedores}


# ── Registry ──────────────────────────────────────────────────────────────────

_LECTURAS: dict[str, Capacidad] = {
    "listar_kpis": Capacidad(
        nombre="listar_kpis",
        descripcion="Lista los indicadores (KPIs) disponibles para el usuario. Arg opcional: categoria.",
        args_schema={"categoria": {"tipo": "str", "requerido": False}},
        gating="abierto", fn=_h_listar_kpis,
    ),
    "consultar_kpi": Capacidad(
        nombre="consultar_kpi",
        descripcion="Devuelve el valor actual de un KPI por su slug (usa listar_kpis para ver los slugs).",
        args_schema={"slug": {"tipo": "str", "requerido": True}},
        gating="abierto", fn=_h_consultar_kpi,
    ),
    "consultar_metrica": Capacidad(
        nombre="consultar_metrica",
        descripcion=(
            "Métrica agregada vía consulta acotada. entidad ∈ {proyecto, tarea, cliente, "
            "egreso, ingreso, recado, buzon_mensaje}; agregacion ∈ {count, sum, avg, min, max}; "
            "campo (para sum/avg/min/max — en egreso/ingreso es 'monto'); "
            "ventana_tiempo ∈ {siempre, ultimos_7d, ultimos_30d, este_mes, este_ano}; "
            "alcance_usuario ∈ {todos, mio}. "
            "filtros: objeto {campo: {op, valor}}. Para buscar por texto usa op 'contiene' "
            "(ej. gasto en ubers este mes → entidad=egreso, agregacion=sum, campo=monto, "
            "ventana_tiempo=este_mes, filtros={\"descripcion\": {\"op\": \"contiene\", \"valor\": \"uber\"}}). "
            "Campos de texto buscables: egreso.descripcion, egreso.proveedor_nombre, ingreso.descripcion."
        ),
        args_schema={
            "entidad": {"tipo": "str", "requerido": True},
            "agregacion": {"tipo": "str", "requerido": False,
                           "enum": ["count", "sum", "avg", "min", "max"]},
            "campo": {"tipo": "str", "requerido": False},
            "ventana_tiempo": {"tipo": "str", "requerido": False,
                               "enum": ["siempre", "ultimos_7d", "ultimos_30d", "este_mes", "este_ano"]},
            "alcance_usuario": {"tipo": "str", "requerido": False, "enum": ["todos", "mio"]},
            "filtros": {"tipo": "any", "requerido": False},
        },
        gating="abierto", fn=_h_consultar_metrica,
    ),
    "detalle_proyecto": Capacidad(
        nombre="detalle_proyecto",
        descripcion="Estatus de un proyecto por código (LC-0001) o slug: incluye costo de producción, utilidad estimada, egresos registrados en Tesorería y deuda por proveedor.",
        args_schema={"proyecto_slug": {"tipo": "str", "requerido": True}},
        gating="abierto", fn=_h_detalle_proyecto,
    ),
    "detalle_cliente": Capacidad(
        nombre="detalle_cliente",
        descripcion="Datos de un cliente por slug o razón social.",
        args_schema={"cliente_slug": {"tipo": "str", "requerido": True}},
        gating="cartera", fn=_h_detalle_cliente,
    ),
    "detalle_factura": Capacidad(
        nombre="detalle_factura",
        descripcion="Estatus de una factura por código (FAC-2026-0001).",
        args_schema={"codigo": {"tipo": "str", "requerido": True}},
        gating="facturacion", fn=_h_detalle_factura,
    ),
    "detalle_cotizacion": Capacidad(
        nombre="detalle_cotizacion",
        descripcion="Estatus de una cotización por código (COT-2026-0001).",
        args_schema={"codigo": {"tipo": "str", "requerido": True}},
        gating="cotizaciones", fn=_h_detalle_cotizacion,
    ),
    "gasto_ia": Capacidad(
        nombre="gasto_ia",
        descripcion="Gasto en IA (costo USD, llamadas, tokens) por proveedor. Arg opcional: dias (default 30).",
        args_schema={"dias": {"tipo": "int", "requerido": False}},
        gating="abierto", fn=_h_gasto_ia,
    ),
    "resumen_finanzas": Capacidad(
        nombre="resumen_finanzas",
        descripcion="Foto económica del negocio: ingresos/egresos/utilidad del mes, margen, saldos (caja/banco/CxC) y utilidad de los últimos 6 meses. Úsala para opinar de finanzas.",
        args_schema={},
        gating="finanzas", fn=_h_resumen_finanzas,
    ),
    "resumen_cobranza": Capacidad(
        nombre="resumen_cobranza",
        descripcion="Estado de la cobranza: CxC total, vencido por antigüedad (1-30/31-60/+60 días), top deudores y conteo de facturas. Úsala para opinar de cobranza.",
        args_schema={},
        gating="finanzas", fn=_h_resumen_cobranza,
    ),
    "resumen_ventas": Capacidad(
        nombre="resumen_ventas",
        descripcion="Pulso de ventas: cotizaciones por estado, conversión aproximada, anticipos por facturar, pipeline de proyectos por estado y facturas cobradas del mes.",
        args_schema={},
        gating="cotizaciones", fn=_h_resumen_ventas,
    ),
    "resumen_margenes": Capacidad(
        nombre="resumen_margenes",
        descripcion="Costos y márgenes del Catálogo: margen promedio, productos/servicios con peor margen y los que no tienen costo capturado. (Este despacho no maneja stock.)",
        args_schema={},
        gating="finanzas", fn=_h_resumen_margenes,
    ),
    "estado_servidor": Capacidad(
        nombre="estado_servidor",
        descripcion="Estado del servidor: CPU, memoria, disco, containers. Arg opcional: detallado (incluye integraciones).",
        args_schema={"detallado": {"tipo": "bool", "requerido": False}},
        gating="abierto", fn=_h_estado_servidor,
    ),
    "specs_servidor": Capacidad(
        nombre="specs_servidor",
        descripcion="Especificaciones del servidor: cores de CPU, RAM total, disco total, uptime.",
        args_schema={},
        gating="abierto", fn=_h_specs_servidor,
    ),
    "detalle_ingreso": Capacidad(
        nombre="detalle_ingreso",
        descripcion="Estatus de un ingreso por código (ING-2026-0001).",
        args_schema={"codigo": {"tipo": "str", "requerido": True}},
        gating="finanzas", fn=_h_detalle_ingreso,
    ),
    "detalle_tarea": Capacidad(
        nombre="detalle_tarea",
        descripcion="Detalle de una tarea por su id numérico.",
        args_schema={"tarea_id": {"tipo": "int", "requerido": True}},
        gating="abierto", fn=_h_detalle_tarea,
    ),
    "mis_tareas": Capacidad(
        nombre="mis_tareas",
        descripcion="Las tareas abiertas asignadas al usuario actual, ordenadas por fecha.",
        args_schema={},
        gating="abierto", fn=_h_mis_tareas,
    ),
    "tareas_de_proyecto": Capacidad(
        nombre="tareas_de_proyecto",
        descripcion="Tareas de un proyecto por código (LC-0001) o slug. Arg opcional: solo_abiertas (default true).",
        args_schema={"proyecto_slug": {"tipo": "str", "requerido": True},
                     "solo_abiertas": {"tipo": "bool", "requerido": False}},
        gating="abierto", fn=_h_tareas_de_proyecto,
    ),
    "contaduria_saldo_cuenta": Capacidad(
        nombre="contaduria_saldo_cuenta",
        descripcion="Saldo de una cuenta contable por código, slot (caja, banco, cxc…) o nombre.",
        args_schema={"cuenta": {"tipo": "str", "requerido": True}},
        gating="contaduria", fn=_h_contaduria_saldo_cuenta,
    ),
    "contaduria_balance": Capacidad(
        nombre="contaduria_balance",
        descripcion="Balance de comprobación: saldo por cuenta con movimiento.",
        args_schema={},
        gating="contaduria", fn=_h_contaduria_balance,
    ),
    "proximos_eventos": Capacidad(
        nombre="proximos_eventos",
        descripcion="Entregas de proyectos y tareas con fecha en los próximos N días (default 14). Arg opcional: dias.",
        args_schema={"dias": {"tipo": "int", "requerido": False}},
        gating="abierto", fn=_h_proximos_eventos,
    ),
    "buscar": Capacidad(
        nombre="buscar",
        descripcion=(
            "Búsqueda libre por texto en proyectos, clientes, facturas y cotizaciones "
            "(cada tipo según tus permisos). Arg: texto (mínimo 2 caracteres)."
        ),
        args_schema={"texto": {"tipo": "str", "requerido": True}},
        gating="abierto", fn=_h_buscar,
    ),
    "buscar_catalogo": Capacidad(
        nombre="buscar_catalogo",
        descripcion=(
            "Busca productos y proveedores del Catálogo por nombre. Devuelve "
            "precio, costo, margen y quién surte cada producto. Arg: texto "
            "(mínimo 2 caracteres)."
        ),
        args_schema={"texto": {"tipo": "str", "requerido": True}},
        gating="catalogo", fn=_h_buscar_catalogo,
    ),
    "mi_jornada_hoy": Capacidad(
        nombre="mi_jornada_hoy",
        descripcion="Tu jornada de hoy en El Checador: entrada, salida, retardo y si tienes un cronómetro de proyecto activo.",
        args_schema={},
        gating="abierto", fn=_h_mi_jornada_hoy,
    ),
    "mis_horas_semana": Capacidad(
        nombre="mis_horas_semana",
        descripcion="Tus horas trabajadas, días, retardos y visitas de los últimos 7 días (El Checador).",
        args_schema={},
        gating="abierto", fn=_h_mis_horas_semana,
    ),
}


# ── Registro ──────────────────────────────────────────────────────────────────
# Registra todas las lecturas en el registro único `capacidades`.
for _cap in _LECTURAS.values():
    registrar(_cap)
