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
    c = Cliente.objects.filter(slug=slug).first()
    if c is None:
        # LC 2026-07-26: si no es el slug, se identifica por razón social o RFC
        # (mismo resolvedor que usan los ejecutores).
        from apps.el_dictado.ejecutores.basicos import _cliente_por_razon_social
        c = (_cliente_por_razon_social(args["cliente_slug"].strip().lstrip("$"))
             or Cliente.objects.filter(razon_social__icontains=slug).first())
    if c is None:
        return {"error": "no_encontrado", "cliente_slug": slug}
    return {
        "razon_social": c.razon_social,
        "estado": c.get_estado_display(),
        "rfc": c.rfc or None,
        # Todas las razones sociales con las que puede facturar (pueden ser varias).
        "razones_sociales": [
            {"razon_social": r.razon_social, "rfc": r.rfc or None, "principal": r.principal}
            for r in c.razones_sociales.all()[:10]
        ],
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


def _resumen_de(dominio: str, usuario=None) -> dict:
    """Un tema de negocio, listo para leer. Fuente única: `taller_home.negocio`."""
    from apps.taller_home.negocio import hechos_de

    h = hechos_de(dominio, usuario)
    return {"dominio": dominio, "titulo": h["titulo"], "resumen": h["hechos"] or "Sin datos."}


def _h_resumen_rentabilidad(args: dict, usuario) -> dict:
    return _resumen_de("rentabilidad", usuario)


def _h_resumen_perdidos(args: dict, usuario) -> dict:
    return _resumen_de("perdidos", usuario)


def _h_resumen_clientes(args: dict, usuario) -> dict:
    return _resumen_de("clientes", usuario)


def _h_resumen_proveedores(args: dict, usuario) -> dict:
    return _resumen_de("proveedores", usuario)


def _h_resumen_equipo(args: dict, usuario) -> dict:
    # `hechos_equipo` recibe al usuario y esconde las horas de quien no le toca ver.
    return _resumen_de("equipo", usuario)


def _h_resumen_ia(args: dict, usuario) -> dict:
    return _resumen_de("ia", usuario)


def _h_rentabilidad_proyecto(args: dict, usuario) -> dict:
    """Cuánto dejó UN proyecto: ingreso, costos, utilidad y margen."""
    from apps.los_proyectos import rentabilidad as rent
    from apps.los_proyectos.mano_obra import horas_por_proyecto
    from apps.los_proyectos.models import Proyecto

    clave = (args.get("proyecto_slug") or "").strip().lstrip("#")
    if not clave:
        return {"error": "Falta el proyecto."}
    proyecto = (
        Proyecto.objects.select_related("cliente")
        .filter(codigo__iexact=clave).first()
        or Proyecto.objects.select_related("cliente").filter(slug__iexact=clave).first()
        or Proyecto.objects.select_related("cliente")
        .filter(nombre__icontains=clave).first()
    )
    if not proyecto:
        return {"error": f"No encontré el proyecto «{clave}»."}
    from datetime import date, timedelta

    hoy = date.today()
    horas = horas_por_proyecto(hoy - timedelta(days=365), hoy).get(proyecto.pk)
    fila = rent.rentabilidad_de(proyecto, horas)
    if fila.get("horas_estimadas_flag"):
        fila["aviso"] = (
            "Las horas son en parte estimadas: se reparte la jornada entre los "
            "proyectos que la persona tocó ese día."
        )
    return fila


def _h_serie_kpi(args: dict, usuario) -> dict:
    """Cómo viene un indicador: su serie, su tendencia y el cambio contra antes."""
    from apps.taller_home import series
    from apps.taller_home.kpis import kpi_por_slug

    slug = (args.get("slug") or "").strip()
    if not slug:
        return {"error": "Falta el indicador."}
    kpi = kpi_por_slug(slug)
    if kpi is None:
        return {"error": f"No existe el indicador «{slug}». Usa listar_kpis para verlos."}
    dias = args.get("dias") or 30
    try:
        dias = max(7, min(int(dias), 365))
    except (TypeError, ValueError):
        dias = 30
    s = series.serie(slug, dias=dias)
    if not s:
        return {"slug": slug, "titulo": kpi.titulo, "hay_historia": False,
                "aviso": "Todavía no hay historia de este indicador; se guarda una foto al día."}
    return {
        "slug": slug, "titulo": kpi.titulo, "hay_historia": True,
        "dias": dias, "muestras": len(s),
        "primero": s[0], "ultimo": s[-1],
        "minimo": min(x["valor"] for x in s), "maximo": max(x["valor"] for x in s),
        "tendencia": series.tendencia(slug),
        "comparacion": series.comparar(slug, dias=min(dias, 30)),
        "serie": s[-30:],
    }


def _h_comparar_kpi(args: dict, usuario) -> dict:
    """Este periodo contra el anterior del mismo largo."""
    from apps.taller_home import series
    from apps.taller_home.kpis import kpi_por_slug

    slug = (args.get("slug") or "").strip()
    kpi = kpi_por_slug(slug) if slug else None
    if kpi is None:
        return {"error": f"No existe el indicador «{slug}»."}
    dias = args.get("dias") or 30
    try:
        dias = max(2, min(int(dias), 180))
    except (TypeError, ValueError):
        dias = 30
    return {"slug": slug, "titulo": kpi.titulo, **series.comparar(slug, dias=dias)}


def _h_kpis_a_mirar_hoy(args: dict, usuario) -> dict:
    """Los pocos indicadores que hoy merecen atención, y por qué cada uno."""
    from apps.taller_home.curaduria import destacados_de_hoy

    filas = destacados_de_hoy(usuario)
    if not filas:
        return {"hay_algo": False,
                "resumen": "Nada se salió de lo normal ni está en alerta hoy."}
    return {
        "hay_algo": True,
        "destacados": [
            {"titulo": f["titulo"], "valor": f["valor"], "razon": f["razon"],
             "tendencia": f["tendencia"], "slug": f["slug"]}
            for f in filas
        ],
    }


def _h_anomalias_kpi(args: dict, usuario) -> dict:
    """Qué indicadores se salieron de su comportamiento normal."""
    from apps.taller_home import series
    from apps.taller_home.kpis import kpis_aplicables_a_rol

    raros = []
    for kpi in kpis_aplicables_a_rol(getattr(usuario, "rol", ""), user=usuario):
        try:
            valor = kpi.calcular(usuario).get("valor")
        except Exception:  # noqa: BLE001
            continue
        if isinstance(valor, str):
            continue
        r = series.es_raro(kpi.slug, valor)
        if r.get("raro"):
            raros.append({
                "slug": kpi.slug, "titulo": kpi.titulo, "valor": valor,
                "normal_ronda": r["mediana"], "desviacion_pct": r["desviacion_pct"],
                "hacia": r["motivo"],
            })
    return {"cuantos": len(raros), "anomalias": raros[:10]} if raros else {
        "cuantos": 0, "resumen": "Todo dentro de lo normal.",
    }


def _h_metas_sugeridas(args: dict, usuario) -> dict:
    """Metas realistas para los indicadores que aún no tienen una."""
    from apps.taller_home.curaduria import proponer_metas

    props = proponer_metas()
    return {"cuantas": len(props), "propuestas": props} if props else {
        "cuantas": 0,
        "resumen": "Sin historia suficiente para proponer metas, o ya todas tienen una.",
    }


def _h_ruta_del_dia(args: dict, usuario) -> dict:
    """La vuelta de hoy de un runner: paradas en orden y kilómetros.

    Si alguien ya le PLANEÓ la ruta (S-Planeador-Rutas), ésa es la respuesta: es
    la que trae el orden que decidió una persona y las citas respetadas. Sólo si
    no hay ruta guardada se calcula al vuelo, que es el comportamiento de antes.
    """
    from apps.el_pizarron.ruta import ruta_de

    guardada = _ruta_guardada_de(usuario)
    if guardada is not None:
        return guardada

    r = ruta_de(usuario)
    if not r["paradas"]:
        return {"hay_ruta": False, "resumen": "No traes mandados abiertos."}
    return {
        "hay_ruta": True,
        "paradas": [
            {"orden": i + 1, "que": p["titulo"], "cliente": p["cliente"],
             "lugar": p["lugar"], "ubicado": p["lat"] is not None}
            for i, p in enumerate(r["paradas"])
        ],
        "total_km": r["total_km"],
        "sin_ubicar": r["sin_ubicar"],
    }


def _ruta_guardada_de(usuario, fecha=None) -> dict | None:
    """La ruta planeada de esa persona para ese día, o None si no hay.

    Devuelve la MISMA forma que `_h_ruta_del_dia` para que el LLM no tenga que
    distinguir de dónde salió la respuesta.
    """
    import datetime as dt

    from apps.el_pizarron.models.ruta import ESTADOS_RUTA_VIVOS, Ruta

    ruta = (
        Ruta.objects.filter(
            fecha=fecha or dt.date.today(), runner=usuario,
            estado__in=ESTADOS_RUTA_VIVOS,
        )
        .prefetch_related("paradas__mandado__tarea__proyecto__cliente")
        .first()
    )
    if ruta is None:
        return None
    paradas = []
    for parada in ruta.paradas.all():
        tarea = parada.mandado.tarea
        proyecto = getattr(tarea, "proyecto", None)
        cliente = getattr(proyecto, "cliente", None)
        paradas.append({
            "orden": parada.orden,
            "que": tarea.titulo,
            "cliente": cliente.razon_social if cliente is not None else "",
            "lugar": parada.etiqueta,
            "ubicado": parada.lat is not None,
            "cita": parada.hora_cita.strftime("%H:%M") if parada.hora_cita else "",
            "llegada_estimada": (
                parada.llegada_estimada.strftime("%H:%M")
                if parada.llegada_estimada else ""
            ),
            "estado": parada.mandado.estado,
        })
    return {
        "hay_ruta": bool(paradas),
        "planeada": True,
        "estado_ruta": ruta.estado,
        "sale_de": ruta.origen_etiqueta or "",
        "redonda": ruta.es_redonda,
        "paradas": paradas,
        "total_km": ruta.distancia_km,
        "sin_ubicar": sum(1 for x in paradas if not x["ubicado"]),
    }


def _h_rutas_planeadas(args: dict, usuario) -> dict:
    """Las rutas planeadas de un día: quién lleva qué y en qué orden.

    Es la vista de quien ORGANIZA el reparto, así que va con permiso. Un runner
    que sólo tiene `rutas.ver` recibe únicamente la suya: leer la vuelta de un
    compañero no es asunto suyo.
    """
    import datetime as dt

    from apps.el_pizarron.models.ruta import ESTADOS_RUTA_VIVOS, Ruta

    from lib.permisos import puede_planear_rutas

    texto = (args.get("fecha") or "").strip()
    try:
        fecha = dt.date.fromisoformat(texto) if texto else dt.date.today()
    except ValueError:
        return {"error": f"Fecha no válida: {texto!r}. Se espera AAAA-MM-DD."}

    qs = (
        Ruta.objects.filter(fecha=fecha, estado__in=ESTADOS_RUTA_VIVOS)
        .select_related("runner")
        .prefetch_related("paradas__mandado__tarea__proyecto__cliente")
    )
    if not puede_planear_rutas(usuario):
        qs = qs.filter(runner=usuario)

    nombre = (args.get("runner") or "").strip()
    if nombre:
        from django.db.models import Q
        qs = qs.filter(
            Q(runner__nombre_completo__icontains=nombre)
            | Q(runner__email__icontains=nombre)
        )

    rutas = []
    for ruta in qs:
        detalle = _ruta_guardada_de(ruta.runner, fecha) or {}
        rutas.append({
            "runner": ruta.runner.nombre_completo,
            "estado": ruta.estado,
            "km_estimados": ruta.distancia_km,
            "paradas": detalle.get("paradas", []),
        })
    if not rutas:
        return {"fecha": str(fecha), "rutas": [],
                "nota": "No hay rutas planeadas para ese día."}
    return {"fecha": str(fecha), "rutas": rutas,
            "nota": "Los kilómetros y las horas son estimados (línea recta)."}

def _h_sugerir_runner(args: dict, usuario) -> dict:
    """A quién conviene darle una entrega, y por qué.

    Considera si está trabajando, cuántos pendientes trae, qué tan lejos está,
    si le queda de paso y si tiene un compromiso encima.
    """
    from apps.el_pizarron.models import Tarea
    from apps.el_pizarron.runners import evaluar_runners

    clave = (args.get("tarea") or "").strip()
    if not clave:
        return {"error": "Falta la tarea."}
    tarea = None
    if clave.isdigit():
        tarea = Tarea.objects.filter(pk=int(clave)).first()
    if tarea is None:
        tarea = Tarea.objects.filter(titulo__icontains=clave, archivada=False).first()
    if tarea is None:
        return {"error": f"No encontré la tarea «{clave}»."}

    filas = evaluar_runners(tarea)
    if not filas:
        return {"hay_candidatos": False,
                "resumen": "Nadie tiene el permiso de recibir mandados."}
    return {
        "hay_candidatos": True,
        "tarea": tarea.titulo,
        "recomendado": filas[0]["runner"].nombre_completo,
        "por_que": ", ".join(filas[0]["razones"]),
        "candidatos": [
            {"quien": f["runner"].nombre_completo, "puntaje": f["puntaje"],
             "razones": f["razones"]}
            for f in filas[:5]
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


def _h_ultima_limpieza(args: dict, usuario) -> dict:
    """Cuándo se soltó por última vez el caché, la RAM y el disco, y qué liberó.

    Es de LECTURA a propósito: correrla es un botón de la pantalla (El Site o la
    pared del NUC), no algo que El Chalán dispare por su cuenta. Es
    mantenimiento de la máquina, no una acción del negocio — el mismo criterio
    que los barridos de aprendizajes, que también son de back-office.
    """
    try:
        from lib.site import limpieza
        r = limpieza.ultima()
    except Exception:  # noqa: BLE001 — sin Redis no hay memoria de esto
        return {"disponible": False}
    comun = {
        "corriendo_ahora": limpieza.corriendo(),
        "como_se_corre": ("con el botón «🧹 Limpiar ahora» de El Site (La Gerencia) "
                          "o de la pared del NUC; también sola cada tres días, "
                          "después del respaldo"),
    }
    if not r:
        return {**comun, "disponible": True, "hubo_corrida": False,
                "nota": "no se ha corrido desde la pantalla"}
    return {
        **comun,
        "disponible": True,
        "hubo_corrida": True,
        "cuando": r.get("cuando"),
        "quien": r.get("quien"),
        "segundos": r.get("segundos"),
        "liberado_mb": r.get("liberado_mb"),
        "resumen": r.get("resumen"),
        "pasos_con_problemas": r.get("problemas"),
        "pasos": {p["clave"]: p["estado"] for p in r.get("pasos") or []},
    }


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
    from django.db.models import Q
    productos = []
    for s in (
        # LC 2026-07-26: también encuentra por el ALIAS con el que se vendió en
        # algún proyecto («TShirt Modelo Janet» → la playera del catálogo).
        Servicio.activos.filter(
            Q(nombre__icontains=texto) | Q(en_proyectos__nombre_proyecto__icontains=texto)
        ).distinct()
        .select_related("categoria")
        .prefetch_related("proveedores", "en_proyectos")[:_TOP_N]
    ):
        alias = []
        for pp in s.en_proyectos.all():
            nom = (pp.nombre_proyecto or "").strip()
            if nom and nom not in alias:
                alias.append(nom)
        productos.append({
            "nombre": s.nombre,
            "tambien_llamado": alias[:5],
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


def _h_buscar_proveedor(args: dict, usuario) -> dict:
    """Ficha completa de UN proveedor (Oscar 2026-07-25): datos, qué surte con
    sus precios, en qué proyectos anda, cuánto se le debe y qué se le ha pagado.

    Acepta nombre o slug del proveedor. El bloque de dinero (deuda y pagos)
    sólo se arma si el usuario puede ver finanzas — defensa en profundidad: el
    gating de la capacidad es del Catálogo, y la deuda es otra cosa.
    """
    from lib.permisos import puede_ver_finanzas

    texto = (args.get("nombre") or args.get("slug") or "").strip().lstrip("$@#")
    if len(texto) < 2:
        return {"error": "texto_muy_corto"}

    from apps.el_catalogo.models import Proveedor
    prov = (
        Proveedor.objects.filter(razon_social__iexact=texto).first()
        or Proveedor.objects.filter(razon_social__icontains=texto).first()
    )
    if prov is None:
        return {"error": "no_encontrado", "nombre": texto}

    surte = [
        {
            "producto": s.nombre,
            "categoria": s.categoria.nombre if s.categoria_id else None,
            "precio": float(s.precio_base or 0),
            "costo": float(s.costo or 0),
            "margen_pct": round(s.margen_porcentaje, 1),
        }
        for s in prov.servicios.filter(activo=True).select_related("categoria")[:_TOP_N]
    ]

    from apps.los_proyectos.models import Proyecto
    from django.db.models import Q as _Q
    mgr = getattr(Proyecto, "activos", Proyecto.objects)
    proyectos_qs = (
        mgr.filter(_Q(proveedores_asignados__proveedor=prov) | _Q(productos__proveedor=prov))
        .exclude(estado__in=["cancelado", "cerrado"])
        .select_related("cliente").distinct().order_by("-creado_en")[:_TOP_N]
    )
    proyectos = [
        {
            "proyecto": p.nombre or p.codigo,
            "codigo": p.codigo,
            "cliente": p.cliente.razon_social if p.cliente_id else None,
            "estado": p.get_estado_display(),
            "link": f"/proyectos/{p.pk}/",
        }
        for p in proyectos_qs
    ]

    datos = {
        "razon_social": prov.razon_social,
        "activo": prov.activo,
        "contacto": prov.nombre_contacto or None,
        "email": prov.email_contacto or None,
        "telefono": prov.telefono or None,
        "rfc": prov.rfc or None,
        "direccion": prov.direccion or None,
        "surte": surte,
        "total_productos": prov.servicios.filter(activo=True).count(),
        "proyectos_activos": proyectos,
        "link": f"/catalogo/proveedores/{prov.pk}/",
    }

    if not puede_ver_finanzas(usuario):
        return datos

    # Deuda comprometida: lo que los proyectos vigentes le van a deber.
    deuda = 0.0
    for p in proyectos_qs:
        for renglon in p.deuda_por_proveedor():
            if getattr(renglon.get("proveedor"), "pk", None) == prov.pk:
                deuda += float(renglon.get("total") or 0)

    from apps.tesoreria.models import Egreso
    from django.db.models import Sum
    egresos = Egreso.vigentes.filter(proveedor=prov)
    pagado = float(egresos.filter(estado_pago="pagado").aggregate(t=Sum("monto"))["t"] or 0)
    por_pagar = float(
        egresos.exclude(estado_pago="pagado").aggregate(t=Sum("monto"))["t"] or 0
    )
    ultimos = [
        {"codigo": e.codigo, "fecha": e.fecha.isoformat(), "monto": float(e.monto),
         "estado_pago": e.get_estado_pago_display(), "descripcion": e.descripcion[:80]}
        for e in egresos.order_by("-fecha", "-pk")[:5]
    ]
    datos["dinero"] = {
        "deuda_comprometida_en_proyectos": round(deuda, 2),
        "egresos_pagados": pagado,
        "egresos_por_pagar": por_pagar,
        "ultimos_egresos": ultimos,
    }
    return datos


# ── Registry ──────────────────────────────────────────────────────────────────


def _h_listar_plantillas_correo(args: dict, usuario) -> dict:  # noqa: ARG001
    """Qué plantillas hay para mandar, con su slug (que es lo que pide el envío).

    Sin esto, El Chalán tendría que adivinar el slug de una plantilla creada
    ayer y el envío fallaría con un «no existe» que el usuario no puede
    interpretar.
    """
    from ajustes.models import PlantillaCorreo

    # Las PROPIAS van primero, y no es cosmético: el registro poda las listas a
    # los primeros elementos antes de enseñárselas al LLM. Con las de sistema
    # al frente, las que el usuario acaba de crear quedaban fuera del corte y
    # El Chalán no se enteraba de que existen. Se excluye `generico` porque no
    # se elige por nombre: es el molde del texto libre.
    from ajustes.models.alias_remitente import faltan_por_dar_de_alta

    sin_alta = set(faltan_por_dar_de_alta())
    filas = [
        {
            "slug": p.slug,
            "nombre": p.nombre,
            "para_que": p.descripcion or "",
            "sale_de": p.remitente_email or "(el remitente general)",
            # Si el alias no está dado de alta en Google, ese correo sale desde
            # la dirección de siempre y nadie se entera: vale la pena que El
            # Chalán lo pueda avisar antes de mandarlo.
            "ojo_alias_sin_dar_de_alta": p.remitente_email.strip().lower() in sin_alta,
            "del_sistema": p.sistema,
        }
        for p in PlantillaCorreo.enviables().order_by("sistema", "nombre")
    ]
    pendientes = PlantillaCorreo.objects.filter(activa=False, origen="chalan").count()
    return {
        "plantillas": filas,
        "total": len(filas),
        "borradores_sin_revisar": pendientes,
        "direcciones_sin_dar_de_alta": sorted(sin_alta),
    }


# ── Automatizaciones (n8n) ─────────────────────────────────────────────────
# Leer, todo. Escribir, nada por su cuenta: prender o apagar un flujo pasa por
# preview y confirmación humana, porque un flujo activo le manda correos a
# clientes (ver `ejecutores/automatizacion.py`).


def _n8n_apagado() -> dict:
    return {
        "disponible": False,
        "nota": (
            "Las automatizaciones no están conectadas: falta pegar la llave de n8n "
            "en Gerencia → Los Ajustes. Mientras tanto no se pueden ni consultar."
        ),
    }


def _h_listar_flujos(usuario, **kw):
    from lib import n8n

    if not n8n.esta_configurado():
        return _n8n_apagado()
    flujos = n8n.listar_flujos()
    if flujos is None:
        return {"disponible": False, "nota": "n8n no contestó."}
    return {
        "disponible": True,
        "total": len(flujos),
        "flujos": flujos,
        "nota": "Para prender o apagar alguno hay que proponerlo y que un humano confirme.",
    }


def _h_detalle_flujo(usuario, flujo_id: str = "", **kw):
    from lib import n8n

    if not n8n.esta_configurado():
        return _n8n_apagado()
    d = n8n.detalle_flujo(str(flujo_id).strip())
    return d or {"error": f"No se encontró el flujo «{flujo_id}»."}


def _h_ejecuciones_flujo(usuario, flujo_id: str = "", limite: int = 10, **kw):
    from lib import n8n

    if not n8n.esta_configurado():
        return _n8n_apagado()
    try:
        limite = max(1, min(int(limite), n8n.TOPE))
    except (TypeError, ValueError):
        limite = 10
    corridas = n8n.ejecuciones(str(flujo_id).strip() or None, limite)
    if corridas is None:
        return {"disponible": False, "nota": "n8n no contestó."}
    return {"disponible": True, "corridas": corridas}


# ── Papeleo (Paperless) ────────────────────────────────────────────────────
# El archivo del papeleo que no tiene lugar en el sistema: contratos,
# remisiones, comprobantes de proveedor sin CFDI. Se busca por el TEXTO que
# sacó el OCR, así que «la remisión donde firmó Optimist» se encuentra aunque
# el archivo se llame scan_0042.pdf.
#
# Los CFDI NO están aquí: tienen su propio camino, que los liga a su factura.


def _papeleo_apagado() -> dict:
    return {
        "disponible": False,
        "nota": (
            "El archivo de papeleo no está conectado: falta la llave de Paperless "
            "en Gerencia → Papeleo. Mientras tanto no se puede buscar."
        ),
    }


def _h_buscar_papeleo(args: dict, usuario) -> dict:  # noqa: ARG001
    from lib import paperless

    if not paperless.esta_configurado():
        return _papeleo_apagado()
    texto = str(args.get("texto") or "").strip()
    if not texto:
        return {"error": "Dime qué buscar (una palabra que esté dentro del documento)."}
    hallados = paperless.buscar(texto, int(args.get("limite") or 10))
    if hallados is None:
        return {"disponible": False, "nota": "El archivo de papeleo no contestó."}
    if not hallados:
        return {
            "disponible": True, "total": 0, "documentos": [],
            "nota": (
                f"Nada con «{texto}». Ojo: sólo se encuentra lo que ya pasó por el "
                "lector de texto, y un documento recién subido tarda unos minutos."
            ),
        }
    for d in hallados:
        d["abrir"] = paperless.url_web(d["id"])
    return {"disponible": True, "total": len(hallados), "documentos": hallados}


def _h_detalle_papeleo(args: dict, usuario) -> dict:  # noqa: ARG001
    from lib import paperless

    if not paperless.esta_configurado():
        return _papeleo_apagado()
    doc = paperless.detalle(str(args.get("documento_id") or "").strip())
    if not doc:
        return {"error": "No se encontró ese documento en el archivo."}
    doc["abrir"] = paperless.url_web(doc["id"])
    # De quién es, si alguien ya lo dijo. Sale de nuestra base, no de Paperless.
    try:
        from papeleo.models import PapeleoLigado

        doc["de_quien"] = [f.a_quien for f in
                           PapeleoLigado.objects.filter(documento_id=doc["id"])[:5]]
    except Exception:  # noqa: BLE001 — sin la tabla, el documento igual se lee
        doc["de_quien"] = []
    return doc


def _h_papeleo_de(args: dict, usuario) -> dict:  # noqa: ARG001
    """El papeleo ligado a un cliente, proyecto o proveedor."""
    from papeleo.models import PapeleoLigado

    filtros = {}
    for arg, campo in (("cliente", "cliente__razon_social__icontains"),
                       ("proyecto", "proyecto__codigo__iexact"),
                       ("proveedor", "proveedor__razon_social__icontains")):
        valor = str(args.get(arg) or "").strip()
        if valor:
            filtros[campo] = valor
    if not filtros:
        return {"error": "Dime de quién: cliente, proyecto o proveedor."}

    filas = list(PapeleoLigado.objects.filter(**filtros)
                 .select_related("cliente", "proyecto", "proveedor")[:20])
    if not filas:
        return {"total": 0, "documentos": [],
                "nota": "No hay papeleo ligado a eso todavía."}
    return {
        "total": len(filas),
        "documentos": [{"id": f.documento_id, "titulo": f.titulo,
                        "de_quien": f.a_quien, "abrir": f.url_web,
                        "ligado": "solo" if f.automatico else "a mano"}
                       for f in filas],
    }



_LECTURAS: dict[str, Capacidad] = {
    "buscar_papeleo": Capacidad(
        nombre="buscar_papeleo",
        descripcion=(
            "Busca en el archivo de papeleo (contratos, remisiones, comprobantes "
            "de proveedor) por el TEXTO que dice adentro, no por el nombre del "
            "archivo. Los CFDI no están aquí: ésos viven en Facturación. "
            "Args: texto (requerido), limite (opcional)."
        ),
        args_schema={"texto": {"tipo": "str", "requerido": True},
                     "limite": {"tipo": "int", "requerido": False}},
        gating="papeleo", fn=_h_buscar_papeleo,
    ),
    "detalle_papeleo": Capacidad(
        nombre="detalle_papeleo",
        descripcion=(
            "Un documento del archivo: su título, cuándo entró, un pedazo de su "
            "texto y de quién es, si alguien ya lo dijo. Arg: documento_id."
        ),
        args_schema={"documento_id": {"tipo": "str", "requerido": True}},
        gating="papeleo", fn=_h_detalle_papeleo,
    ),
    "papeleo_de": Capacidad(
        nombre="papeleo_de",
        descripcion=(
            "Qué papeleo tiene ligado un cliente, un proyecto o un proveedor. "
            "Args (uno): cliente (nombre), proyecto (código LC-…), proveedor."
        ),
        args_schema={"cliente": {"tipo": "str", "requerido": False},
                     "proyecto": {"tipo": "str", "requerido": False},
                     "proveedor": {"tipo": "str", "requerido": False}},
        gating="papeleo", fn=_h_papeleo_de,
    ),
    "listar_automatizaciones": Capacidad(
        nombre="listar_automatizaciones",
        descripcion=(
            "Las tareas que corren solas (flujos de n8n): cuáles hay, cuáles están "
            "prendidas y qué las dispara. Úsala antes de proponer prender o apagar "
            "alguna, para no inventar un identificador."
        ),
        args_schema={},
        gating="automatizacion", fn=_h_listar_flujos,
    ),
    "detalle_automatizacion": Capacidad(
        nombre="detalle_automatizacion",
        descripcion="Qué hace una automatización paso por paso. Arg: flujo_id.",
        args_schema={"flujo_id": {"tipo": "str", "requerido": True}},
        gating="automatizacion", fn=_h_detalle_flujo,
    ),
    "corridas_automatizacion": Capacidad(
        nombre="corridas_automatizacion",
        descripcion=(
            "Las últimas veces que corrió una automatización y si salió bien. Sin "
            "flujo_id, las de todas. Args: flujo_id (opcional), limite (opcional)."
        ),
        args_schema={"flujo_id": {"tipo": "str", "requerido": False},
                     "limite": {"tipo": "int", "requerido": False}},
        gating="automatizacion", fn=_h_ejecuciones_flujo,
    ),
    "listar_plantillas_correo": Capacidad(
        nombre="listar_plantillas_correo",
        descripcion=(
            "Plantillas de correo disponibles para enviar, con su slug. Úsala antes de "
            "`enviar_correo` si no sabes qué slug pedir, en lugar de inventarlo."
        ),
        args_schema={},
        gating="comunicacion", fn=_h_listar_plantillas_correo,
    ),
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
    "ultima_limpieza": Capacidad(
        nombre="ultima_limpieza",
        descripcion=("Cuándo se corrió La Limpieza del servidor (soltar caché, RAM y "
                     "disco), quién la pidió y qué liberó. Sólo informa: correrla es "
                     "un botón de El Site o de la pared del NUC."),
        args_schema={},
        gating="abierto", fn=_h_ultima_limpieza,
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
    "buscar_proveedor": Capacidad(
        nombre="buscar_proveedor",
        descripcion=(
            "Ficha de UN proveedor por nombre: contacto, qué productos surte "
            "con sus precios y costos, en qué proyectos anda, cuánto se le "
            "debe y qué se le ha pagado (el dinero sólo si puedes ver "
            "finanzas). Arg: nombre."
        ),
        args_schema={"nombre": {"tipo": "str", "requerido": True}},
        gating="catalogo", fn=_h_buscar_proveedor,
    ),
    "resumen_rentabilidad": Capacidad(
        nombre="resumen_rentabilidad",
        descripcion=(
            "Cuánto dejó de verdad cada proyecto: vendido, costo real de "
            "materiales y procesos, utilidad, margen y cuáles están debajo del "
            "margen sano o en pérdida. Incluye el costo del tiempo del equipo "
            "cuando hay tarifas capturadas."
        ),
        args_schema={},
        gating="finanzas", fn=_h_resumen_rentabilidad,
    ),
    "rentabilidad_proyecto": Capacidad(
        nombre="rentabilidad_proyecto",
        descripcion=(
            "La cuenta de UN proyecto por código, slug o nombre: ingreso, costo, "
            "utilidad, margen y horas de mano de obra."
        ),
        args_schema={"proyecto_slug": {"tipo": "str", "requerido": True}},
        gating="finanzas", fn=_h_rentabilidad_proyecto,
    ),
    "resumen_perdidos": Capacidad(
        nombre="resumen_perdidos",
        descripcion=(
            "Lo que se perdió: cotizaciones caídas y su monto, proyectos "
            "cancelados con su motivo, propuestas enfriadas por falta de "
            "respuesta y proyectos que se ganaron pero dejaron pérdida."
        ),
        args_schema={},
        gating="cotizaciones", fn=_h_resumen_perdidos,
    ),
    "resumen_clientes": Capacidad(
        nombre="resumen_clientes",
        descripcion=(
            "Quién deja más dinero, quién debe más, quién dejó de comprar y el "
            "ticket promedio."
        ),
        args_schema={},
        gating="cartera", fn=_h_resumen_clientes,
    ),
    "resumen_proveedores": Capacidad(
        nombre="resumen_proveedores",
        descripcion=(
            "A quién se le compra más, cuánto se le debe a cada quien y qué "
            "egresos quedaron sin proveedor asignado."
        ),
        args_schema={},
        gating="finanzas", fn=_h_resumen_proveedores,
    ),
    "resumen_equipo": Capacidad(
        nombre="resumen_equipo",
        descripcion=(
            "Carga y cumplimiento: tareas pendientes y atrasadas por persona, y "
            "X"
        ),
        args_schema={},
        gating="abierto", fn=_h_resumen_equipo,
    ),
    "resumen_ia": Capacidad(
        nombre="resumen_ia",
        descripcion=(
            "Cuánto cuestan Los Chalanes en los últimos 30 días, repartido por "
            "Chalán, y qué tan seguido fallan las instrucciones dictadas."
        ),
        args_schema={},
        gating="finanzas", fn=_h_resumen_ia,
    ),
    "serie_kpi": Capacidad(
        nombre="serie_kpi",
        descripcion=(
            "Cómo viene un indicador en el tiempo: su serie de los últimos días, "
            "si va subiendo o bajando, y cuánto cambió contra el periodo anterior. "
            "Usa listar_kpis para ver los slugs disponibles."
        ),
        args_schema={"slug": {"tipo": "str", "requerido": True},
                     "dias": {"tipo": "int", "requerido": False}},
        gating="abierto", fn=_h_serie_kpi,
    ),
    "comparar_kpi": Capacidad(
        nombre="comparar_kpi",
        descripcion="Un indicador en este periodo contra el anterior del mismo largo.",
        args_schema={"slug": {"tipo": "str", "requerido": True},
                     "dias": {"tipo": "int", "requerido": False}},
        gating="abierto", fn=_h_comparar_kpi,
    ),
    "kpis_a_mirar_hoy": Capacidad(
        nombre="kpis_a_mirar_hoy",
        descripcion=(
            "Los pocos indicadores que hoy merecen atención —los que están en "
            "alerta, se salieron de lo normal o cambiaron fuerte— con el porqué "
            "de cada uno. Úsala cuando te pregunten «¿cómo vamos?» o «¿qué debo "
            "ver hoy?» en vez de listar todo."
        ),
        args_schema={},
        gating="abierto", fn=_h_kpis_a_mirar_hoy,
    ),
    "anomalias_kpi": Capacidad(
        nombre="anomalias_kpi",
        descripcion=(
            "Qué indicadores se salieron de su comportamiento normal, comparando "
            "cada uno contra su propia historia."
        ),
        args_schema={},
        gating="abierto", fn=_h_anomalias_kpi,
    ),
    "metas_sugeridas": Capacidad(
        nombre="metas_sugeridas",
        descripcion=(
            "Metas realistas para los indicadores que no tienen una, calculadas "
            "con lo que de verdad se ha hecho los últimos meses."
        ),
        args_schema={},
        gating="finanzas", fn=_h_metas_sugeridas,
    ),
    "ruta_del_dia": Capacidad(
        nombre="ruta_del_dia",
        descripcion=(
            "La vuelta de hoy: los mandados abiertos del runner ordenados por "
            "cercanía, con los kilómetros aproximados."
        ),
        args_schema={},
        gating="abierto", fn=_h_ruta_del_dia,
    ),
    "rutas_planeadas": Capacidad(
        nombre="rutas_planeadas",
        descripcion=(
            "Las rutas de reparto PLANEADAS de un día: quién lleva qué, en qué "
            "orden, con la cita y la llegada estimada. Args opcionales: fecha "
            "(AAAA-MM-DD, por default hoy) y runner (nombre o correo). Para tu "
            "propia vuelta usa `ruta_del_dia`."
        ),
        args_schema={
            "fecha": {"tipo": "str", "requerido": False},
            "runner": {"tipo": "str", "requerido": False},
        },
        gating="rutas", fn=_h_rutas_planeadas,
    ),
    "sugerir_runner": Capacidad(
        nombre="sugerir_runner",
        descripcion=(
            "A qué repartidor conviene darle una entrega o recolección, y por "
            "qué: mira quién está en jornada, cuántos pendientes trae, qué tan "
            "lejos está del destino, si le queda de paso y si tiene un "
            "compromiso con hora encima. Arg: tarea (id o parte del título)."
        ),
        args_schema={"tarea": {"tipo": "str", "requerido": True}},
        gating="abierto", fn=_h_sugerir_runner,
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

