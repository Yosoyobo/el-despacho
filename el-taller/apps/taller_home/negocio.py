"""Lecturas de negocio para El Chalán (S-Chalan-Negocio-V1).

Fuente ÚNICA de hechos por dominio. La consumen el chat (herramientas
read-only), el análisis proactivo (`analisis_negocio.py`) y el destilador de
conocimiento (`destilar_negocio.py`) — sin duplicar queries.

Cada función reúne datos REALES reutilizando los servicios existentes
(contaduría, tesorería, facturación, cotizaciones, catálogo) y devuelve:

    {"titulo": str, "hechos": str, "metricas": dict}

`hechos` es texto compacto en español listo para el prompt y para mostrar.
Todas son SOLO LECTURA y defensivas: si algo falla, devuelven hechos="" para
no tumbar al Chalán ni al cron.

Dominios: finanzas · cobranza · ventas · rentabilidad · perdidos · clientes ·
proveedores · equipo · ia.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)

DOMINIOS = (
    "finanzas", "cobranza", "ventas", "rentabilidad", "perdidos",
    "clientes", "proveedores", "equipo", "ia",
)
ETIQUETA_DOMINIO = {
    "finanzas": "Económicos / Finanzas",
    "cobranza": "Cobranza (CxC)",
    "ventas": "Ventas y pipeline",
    "rentabilidad": "Rentabilidad real por proyecto",
    "perdidos": "Lo que se perdió",
    "clientes": "Clientes",
    "proveedores": "Proveedores y compras",
    "equipo": "Carga y cumplimiento del equipo",
    "ia": "Gasto en IA y uso del sistema",
    # Alias histórico: "margenes" era el margen del Catálogo; ahora la pregunta
    # se contesta con la rentabilidad real de los proyectos.
    "margenes": "Rentabilidad real por proyecto",
}

# Dominios que sólo puede ver quien tiene el permiso correspondiente.
# Los usa el análisis proactivo y la pantalla de El Análisis.
PERMISO_DOMINIO = {
    "finanzas": "puede_ver_finanzas",
    "cobranza": "puede_ver_finanzas",
    "ventas": "puede_ver_cotizaciones",
    "rentabilidad": "puede_ver_finanzas",
    "perdidos": "puede_ver_cotizaciones",
    "clientes": "puede_ver_cartera",
    "proveedores": "puede_ver_finanzas",
    "equipo": "puede_ver_equipo_checador",
    "ia": "puede_ver_finanzas",
}


def _money(valor) -> str:
    try:
        return f"${Decimal(valor):,.2f}"
    except Exception:
        return "$0.00"


def _vacio(dominio: str) -> dict:
    return {"titulo": ETIQUETA_DOMINIO.get(dominio, dominio), "hechos": "", "metricas": {}}


# ── Finanzas / económicos ────────────────────────────────────────────


def hechos_finanzas() -> dict:
    """P&L del mes + saldos + tendencia 6 meses."""
    try:
        from apps.contaduria import reportes as conta_reportes
        from apps.contaduria import services as conta_services
        from apps.tesoreria import services as tes_services

        er = conta_reportes.estado_resultados()
        conta = conta_services.kpis_landing()
        series = tes_services.series_mensuales_6m()

        ingresos = er["ingresos"]["total"]
        egresos = er["egresos"]["total"]
        util_op = er["utilidad_operativa"]
        margen = (float(util_op) / float(ingresos) * 100) if ingresos else 0.0

        lineas = [
            f"Periodo: {er['desde']} a {er['hasta']} (mes en curso).",
            f"Ingresos del periodo: {_money(ingresos)}.",
            f"Egresos del periodo: {_money(egresos)}.",
            f"Utilidad operativa: {_money(util_op)} (margen {margen:.1f}%).",
            f"ISR estimado ({er['regimen_label']}, informativo): {_money(er['isr_estimado'])}.",
            f"Saldos contables — Caja: {_money(conta['saldo_caja'])} · "
            f"Banco: {_money(conta['saldo_banco'])} · CxC: {_money(conta['saldo_cxc'])}.",
            f"Asientos del mes: {conta['asientos_mes']}.",
            "Utilidad mensual últimos 6 meses: "
            + ", ".join(_money(v) for v in series.get("utilidad", [])) + ".",
        ]
        return {
            "titulo": ETIQUETA_DOMINIO["finanzas"],
            "hechos": "\n".join(lineas),
            "metricas": {
                "ingresos_mes": float(ingresos), "egresos_mes": float(egresos),
                "utilidad_operativa": float(util_op), "margen_pct": round(margen, 1),
                "saldo_caja": float(conta["saldo_caja"]), "saldo_banco": float(conta["saldo_banco"]),
                "saldo_cxc": float(conta["saldo_cxc"]),
                "utilidad_6m": series.get("utilidad", []),
            },
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_finanzas falló", exc_info=True)
        return _vacio("finanzas")


# ── Cobranza (CxC) ───────────────────────────────────────────────────


def hechos_cobranza() -> dict:
    """CxC unificado: total, aging por antigüedad, top deudores + KPIs factura."""
    try:
        from apps.facturacion import services as fac_services
        from apps.tesoreria import services as tes_services

        filas = tes_services.cxc_unificado()
        hoy = date.today()
        total = sum((f["saldo"] for f in filas), Decimal("0"))

        buckets = {"al_corriente": Decimal("0"), "1_30": Decimal("0"),
                   "31_60": Decimal("0"), "mas_60": Decimal("0")}
        vencido_total = Decimal("0")
        por_cliente: dict[str, Decimal] = {}
        for f in filas:
            saldo = f["saldo"]
            venc = f["fecha_vencimiento"]
            dias = (hoy - venc).days if venc else 0
            if not venc or dias <= 0:
                buckets["al_corriente"] += saldo
            else:
                vencido_total += saldo
                if dias <= 30:
                    buckets["1_30"] += saldo
                elif dias <= 60:
                    buckets["31_60"] += saldo
                else:
                    buckets["mas_60"] += saldo
            cli = f["cliente"] or "—"
            por_cliente[cli] = por_cliente.get(cli, Decimal("0")) + saldo

        top = sorted(por_cliente.items(), key=lambda kv: kv[1], reverse=True)[:5]
        fac = fac_services.kpis_landing()

        lineas = [
            f"CxC total por cobrar: {_money(total)} en {len(filas)} documentos.",
            f"Vencido: {_money(vencido_total)} · Al corriente: {_money(buckets['al_corriente'])}.",
            f"Antigüedad del vencido — 1-30 días: {_money(buckets['1_30'])} · "
            f"31-60: {_money(buckets['31_60'])} · más de 60: {_money(buckets['mas_60'])}.",
            "Top deudores: " + ("; ".join(f"{c} {_money(s)}" for c, s in top) or "ninguno") + ".",
            f"Facturas: {fac['emitidas']} emitidas, {fac['vencidas']} vencidas, "
            f"{fac['cobradas_mes']} cobradas este mes, {fac['borradores']} en borrador.",
        ]
        return {
            "titulo": ETIQUETA_DOMINIO["cobranza"],
            "hechos": "\n".join(lineas),
            "metricas": {
                "cxc_total": float(total), "vencido_total": float(vencido_total),
                "aging": {k: float(v) for k, v in buckets.items()},
                "top_deudores": [{"cliente": c, "saldo": float(s)} for c, s in top],
                "facturas": fac,
            },
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_cobranza falló", exc_info=True)
        return _vacio("cobranza")


# ── Ventas y pipeline ────────────────────────────────────────────────


def hechos_ventas() -> dict:
    """Embudo real: oportunidades por fase, conversión y lo que está parado."""
    try:
        from apps.cotizaciones.embudo import embudo
        from apps.facturacion import services as fac_services
        from apps.los_proyectos.models import Proyecto

        emb = embudo()
        fac = fac_services.kpis_landing()

        pipeline: dict[str, int] = {}
        for p in Proyecto.objects.filter(archivado=False).exclude(
            estado="cancelado"
        ).values("estado"):
            pipeline[p["estado"]] = pipeline.get(p["estado"], 0) + 1

        lineas = [
            f"Oportunidades cotizadas: {emb['total']} "
            f"(una por proyecto; las versiones de una misma cotización no se cuentan aparte).",
            f"Vivas: {emb['vivas']} — {emb['armadas']} armadas sin mandar y "
            f"{emb['enviadas']} en manos del cliente, por {_money(emb['monto_vivo'])}.",
            f"Ganadas: {emb['ganadas']} por {_money(emb['monto_ganado'])}. "
            f"Perdidas: {emb['perdidas']} por {_money(emb['monto_perdido'])}.",
            f"De lo ya resuelto se ganó el {emb['conversion_pct']:.0f}%; "
            f"de todo lo cotizado se ha cerrado el {emb['cierre_pct']:.0f}%.",
        ]
        if emb["sin_enviar"]:
            top = emb["sin_enviar"][:5]
            lineas.append(
                f"ALERTA — {len(emb['sin_enviar'])} cotizaciones armadas que nunca se "
                "mandaron: "
                + "; ".join(f"{f['proyecto']} ({f['cliente']}, {f['dias']}d)" for f in top)
                + "."
            )
        if emb["enfriadas"]:
            top = emb["enfriadas"][:5]
            lineas.append(
                f"ALERTA — {len(emb['enfriadas'])} enviadas sin respuesta hace más de "
                f"{emb['dias_silencio']} días: "
                + "; ".join(f"{f['proyecto']} ({f['cliente']}, {f['dias']}d)" for f in top)
                + "."
            )
        lineas.append(
            "Pipeline de proyectos por estado: "
            + (", ".join(f"{e}={n}" for e, n in sorted(pipeline.items())) or "vacío") + "."
        )
        lineas.append(
            f"Facturas: {fac['facturadas']} facturadas, {fac['vencidas']} vencidas, "
            f"{fac['cobradas_mes']} cobradas este mes."
        )
        if fac.get("cfdi_sin_emitir"):
            lineas.append(
                f"PENDIENTE — {fac['cfdi_sin_emitir']} facturas tienen su CFDI subido "
                "pero siguen en borrador: no generan cuenta por cobrar en Contaduría "
                "ni reciben recordatorio de cobranza."
            )

        return {
            "titulo": ETIQUETA_DOMINIO["ventas"],
            "hechos": "\n".join(lineas),
            "metricas": {"embudo": emb, "pipeline": pipeline, "facturas": fac},
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_ventas falló", exc_info=True)
        return _vacio("ventas")


# ── Rentabilidad real de los proyectos ───────────────────────────────


def hechos_rentabilidad() -> dict:
    """Lo que de verdad dejó cada proyecto — no el precio de lista del Catálogo.

    Antes este dominio miraba el margen teórico del Catálogo (precio contra
    costo de lista). Con proyectos reales capturados, la pregunta que importa
    es otra: en cuáles se ganó y en cuáles se perdió.
    """
    try:
        from apps.los_proyectos import rentabilidad as rent
        from apps.los_proyectos.mano_obra import hay_tarifas_configuradas

        filas = rent.tabla()
        res = rent.resumen(filas)

        lineas = [
            f"Proyectos con dinero capturado: {res['proyectos']}.",
            f"Vendido: {_money(res['ingreso'])} · Costo de materiales y procesos: "
            f"{_money(res['costo_materiales'])} · Utilidad: {_money(res['utilidad'])} "
            f"({res['margen_pct']:.0f}% de margen).",
            f"Margen sano configurado: {res['margen_sano_pct']:.0f}%.",
        ]
        if res["costo_mano_obra"]:
            lineas.append(
                f"Costo del tiempo del equipo: {_money(res['costo_mano_obra'])} → "
                f"utilidad después de mano de obra {_money(res['utilidad_con_mano_obra'])} "
                f"({res['margen_con_mano_obra_pct']:.0f}%). "
                "Ojo: buena parte de esas horas son estimadas."
            )
        elif not hay_tarifas_configuradas():
            lineas.append(
                "No se puede costear la mano de obra todavía: falta capturar el costo "
                "por hora en Gerencia → Ajustes → El Análisis."
            )
        if res["en_perdida"]:
            lineas.append(
                f"EN PÉRDIDA ({res['n_en_perdida']}): "
                + "; ".join(
                    f"{f['nombre']} ({f['cliente']}) {f['margen_materiales_pct']:.0f}%"
                    for f in res["en_perdida"][:5]
                ) + "."
            )
        if res["bajo_umbral"]:
            lineas.append(
                f"Debajo del margen sano ({res['n_bajo_umbral']}): "
                + "; ".join(
                    f"{f['nombre']} ({f['cliente']}) {f['margen_materiales_pct']:.0f}%"
                    for f in res["bajo_umbral"][:5]
                ) + "."
            )
        mejores = sorted(
            (f for f in filas if f["margen_materiales_pct"] is not None),
            key=lambda f: -f["margen_materiales_pct"],
        )[:3]
        if mejores:
            lineas.append(
                "Los que mejor pagaron: "
                + "; ".join(
                    f"{f['nombre']} {f['margen_materiales_pct']:.0f}%" for f in mejores
                ) + "."
            )

        return {
            "titulo": ETIQUETA_DOMINIO["rentabilidad"],
            "hechos": "\n".join(lineas),
            "metricas": {"resumen": res, "peores": filas[:10], "mejores": mejores},
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_rentabilidad falló", exc_info=True)
        return _vacio("rentabilidad")


# Alias: el dominio se llamaba "margenes".
def hechos_margenes() -> dict:
    return hechos_rentabilidad()


# ── Lo que se perdió ─────────────────────────────────────────────────


def hechos_perdidos() -> dict:
    """Cotizaciones caídas, proyectos cancelados y trabajo que costó más de lo que dejó."""
    try:
        from datetime import timedelta

        from apps.cotizaciones.embudo import embudo, perdidas_del_periodo
        from apps.los_proyectos import rentabilidad as rent
        from apps.los_proyectos.models import Proyecto

        hoy = date.today()
        desde = hoy - timedelta(days=365)
        emb = embudo()
        caidas = perdidas_del_periodo(desde, hoy)

        cancelados = list(
            Proyecto.objects.filter(estado="cancelado", archivado=False)
            .select_related("cliente", "motivo_cancelacion")
            .order_by("-cancelado_en", "-pk")[:50]
        )
        por_motivo: dict[str, int] = {}
        for p in cancelados:
            etiqueta = (
                p.motivo_cancelacion.label if p.motivo_cancelacion_id else "Sin información"
            )
            por_motivo[etiqueta] = por_motivo.get(etiqueta, 0) + 1

        res = rent.resumen()
        perdida_dinero = res["en_perdida"]

        lineas = [
            f"Cotizaciones perdidas: {emb['perdidas']} por {_money(emb['monto_perdido'])}.",
            f"Proyectos cancelados: {len(cancelados)}. Motivos: "
            + (", ".join(f"{m} ({n})" for m, n in sorted(
                por_motivo.items(), key=lambda kv: -kv[1])) or "sin registrar") + ".",
        ]
        if caidas:
            lineas.append(
                "Últimas caídas: "
                + "; ".join(
                    f"{c['proyecto'] or c['codigo']} ({c['cliente']}, {_money(c['monto'])}"
                    + (f" — {c['motivo'][:60]}" if c["motivo"] else "") + ")"
                    for c in caidas[:5]
                ) + "."
            )
        if emb["enfriadas"]:
            lineas.append(
                f"En riesgo de perderse: {len(emb['enfriadas'])} cotizaciones llevan más de "
                f"{emb['dias_silencio']} días sin respuesta."
            )
        if perdida_dinero:
            lineas.append(
                f"Ganados pero con pérdida ({res['n_en_perdida']}): "
                + "; ".join(
                    f"{f['nombre']} ({f['cliente']}) {f['margen_materiales_pct']:.0f}%"
                    for f in perdida_dinero[:5]
                ) + "."
            )
        sin_motivo = por_motivo.get("Sin información", 0)
        if sin_motivo:
            lineas.append(
                f"{sin_motivo} cancelaciones no tienen motivo capturado — sin eso no se "
                "puede saber por qué se pierde el trabajo."
            )

        return {
            "titulo": ETIQUETA_DOMINIO["perdidos"],
            "hechos": "\n".join(lineas),
            "metricas": {
                "cotizaciones_perdidas": emb["perdidas"],
                "monto_perdido": emb["monto_perdido"],
                "cancelados": len(cancelados),
                "por_motivo": por_motivo,
                "caidas": caidas[:10],
                "enfriadas": emb["enfriadas"][:10],
                "en_perdida": perdida_dinero[:10],
            },
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_perdidos falló", exc_info=True)
        return _vacio("perdidos")


# ── Clientes ─────────────────────────────────────────────────────────


def hechos_clientes() -> dict:
    """Quién deja dinero, quién debe, quién dejó de comprar."""
    try:
        from datetime import timedelta

        from apps.la_cartera.models import Cliente
        from apps.tesoreria import services as tes_services
        from apps.tesoreria.models import Ingreso
        from django.db.models import Count, Sum

        hoy = date.today()
        hace_un_ano = hoy - timedelta(days=365)

        ingresos = (
            Ingreso.vigentes.filter(fecha__gte=hace_un_ano, cliente__isnull=False)
            .values("cliente__razon_social")
            .annotate(total=Sum("monto"), n=Count("pk"))
            .order_by("-total")[:10]
        )
        top = [
            {"cliente": i["cliente__razon_social"], "total": float(i["total"] or 0),
             "movimientos": i["n"]}
            for i in ingresos
        ]

        deuda: dict[str, float] = {}
        try:
            for f in tes_services.cxc_unificado():
                nombre = f["cliente"] or "—"
                deuda[nombre] = deuda.get(nombre, 0.0) + float(f["saldo"])
        except Exception:  # noqa: BLE001
            pass
        morosos = sorted(deuda.items(), key=lambda kv: -kv[1])[:5]

        activos = Cliente.activos.count() if hasattr(Cliente, "activos") else Cliente.objects.count()
        con_proyecto = (
            Cliente.objects.filter(proyectos__isnull=False).distinct().count()
        )
        dormidos = (
            Cliente.objects.filter(proyectos__isnull=False)
            .exclude(proyectos__creado_en__date__gte=hace_un_ano)
            .distinct()[:10]
        )

        lineas = [
            f"Clientes en el padrón: {activos}. Con al menos un proyecto: {con_proyecto}.",
            "Los que más dejaron (12 meses): "
            + ("; ".join(f"{c['cliente']} {_money(c['total'])}" for c in top[:5])
               or "sin ingresos registrados") + ".",
            "Los que más deben: "
            + ("; ".join(f"{n} {_money(s)}" for n, s in morosos) or "nadie") + ".",
        ]
        nombres_dormidos = [c.razon_social for c in dormidos]
        if nombres_dormidos:
            lineas.append(
                f"Sin proyectos nuevos en un año ({len(nombres_dormidos)}): "
                + ", ".join(nombres_dormidos[:8]) + "."
            )
        ticket = (sum(c["total"] for c in top) / sum(c["movimientos"] for c in top)) if top else 0
        if ticket:
            lineas.append(f"Ticket promedio de los mejores clientes: {_money(ticket)}.")

        return {
            "titulo": ETIQUETA_DOMINIO["clientes"],
            "hechos": "\n".join(lineas),
            "metricas": {
                "activos": activos, "con_proyecto": con_proyecto,
                "top_ingresos": top,
                "top_deuda": [{"cliente": n, "saldo": s} for n, s in morosos],
                "dormidos": nombres_dormidos,
            },
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_clientes falló", exc_info=True)
        return _vacio("clientes")


# ── Proveedores y compras ────────────────────────────────────────────


def hechos_proveedores() -> dict:
    """A quién le compramos, a quién le debemos, quién se encareció."""
    try:
        from datetime import timedelta

        from apps.tesoreria.models import Egreso
        from django.db.models import Count, Sum

        hoy = date.today()
        hace_un_ano = hoy - timedelta(days=365)

        compras = (
            Egreso.vigentes.filter(fecha__gte=hace_un_ano)
            .values("proveedor__razon_social")
            .annotate(total=Sum("monto"), n=Count("pk"))
            .order_by("-total")[:10]
        )
        top = [
            {"proveedor": c["proveedor__razon_social"] or "Sin proveedor",
             "total": float(c["total"] or 0), "movimientos": c["n"]}
            for c in compras
        ]
        por_pagar = (
            Egreso.vigentes.exclude(estado_pago="pagado")
            .values("proveedor__razon_social")
            .annotate(total=Sum("monto"))
            .order_by("-total")[:10]
        )
        deuda = [
            {"proveedor": d["proveedor__razon_social"] or "Sin proveedor",
             "total": float(d["total"] or 0)}
            for d in por_pagar
        ]
        total_deuda = sum(d["total"] for d in deuda)
        sin_proveedor = Egreso.vigentes.filter(
            fecha__gte=hace_un_ano, proveedor__isnull=True
        ).count()

        lineas = [
            "A quién más se le compró (12 meses): "
            + ("; ".join(f"{c['proveedor']} {_money(c['total'])} en {c['movimientos']} compras"
                         for c in top[:5]) or "sin compras registradas") + ".",
            f"Por pagar: {_money(total_deuda)}. "
            + ("Los mayores: " + "; ".join(f"{d['proveedor']} {_money(d['total'])}"
                                           for d in deuda[:5]) + "." if deuda else ""),
        ]
        if sin_proveedor:
            lineas.append(
                f"{sin_proveedor} egresos del último año no tienen proveedor asignado — "
                "sin eso no se puede saber a quién se le compra."
            )

        return {
            "titulo": ETIQUETA_DOMINIO["proveedores"],
            "hechos": "\n".join(lineas),
            "metricas": {
                "top_compras": top, "por_pagar": deuda,
                "total_por_pagar": round(total_deuda, 2),
                "egresos_sin_proveedor": sin_proveedor,
            },
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_proveedores falló", exc_info=True)
        return _vacio("proveedores")


# ── Carga y cumplimiento del equipo ──────────────────────────────────


def hechos_equipo(usuario=None) -> dict:
    """Quién trae qué, qué se está entregando tarde y cuánto se trabajó.

    Respeta la regla de privacidad del repo: las horas de una persona sólo las
    ve ella, su jefe directo o el super admin. Si `usuario` no puede ver a
    alguien, esa persona no aparece con nombre en las horas.
    """
    try:
        from datetime import timedelta

        from apps.el_pizarron.models import Tarea

        from lib.permisos import puede_ver_horas_trabajadas_de

        hoy = date.today()
        hace_semana = hoy - timedelta(days=7)

        pendientes = (
            Tarea.objects.filter(archivada=False)
            .exclude(estado__in=("completada", "cancelada"))
            .select_related("asignada_a", "proyecto")
        )
        atrasadas = [t for t in pendientes if getattr(t, "esta_atrasada", False)]

        por_persona: dict[str, dict] = {}
        for t in pendientes:
            nombre = t.asignada_a.nombre_completo if t.asignada_a_id else "Sin asignar"
            fila = por_persona.setdefault(nombre, {"pendientes": 0, "atrasadas": 0})
            fila["pendientes"] += 1
            if getattr(t, "esta_atrasada", False):
                fila["atrasadas"] += 1

        lineas = [
            f"Tareas pendientes: {pendientes.count()}. Atrasadas: {len(atrasadas)}.",
            "Carga por persona: "
            + ("; ".join(
                f"{n} {d['pendientes']}" + (f" ({d['atrasadas']} atrasadas)" if d["atrasadas"] else "")
                for n, d in sorted(por_persona.items(), key=lambda kv: -kv[1]["pendientes"])[:8]
            ) or "nadie con tareas") + ".",
        ]

        # Horas de la semana — sólo de quien el lector puede ver.
        try:
            from apps.checador.models import Jornada

            jornadas = Jornada.objects.filter(fecha__gte=hace_semana).select_related("usuario")
            horas: dict[str, float] = {}
            for j in jornadas:
                if usuario is not None and not puede_ver_horas_trabajadas_de(usuario, j.usuario):
                    continue
                h = j.horas_trabajadas or 0
                if h:
                    horas[j.usuario.nombre_completo] = horas.get(j.usuario.nombre_completo, 0) + h
            if horas:
                lineas.append(
                    "Horas de los últimos 7 días: "
                    + "; ".join(f"{n} {h:.1f} h" for n, h in
                                sorted(horas.items(), key=lambda kv: -kv[1])[:8]) + "."
                )
        except Exception:  # noqa: BLE001
            pass

        if atrasadas:
            lineas.append(
                "Lo más atrasado: "
                + "; ".join(
                    f"{t.titulo[:40]}"
                    + (f" · {t.proyecto.nombre}" if t.proyecto_id else "")
                    + (f" · {t.asignada_a.nombre_completo}" if t.asignada_a_id else " · sin dueño")
                    for t in atrasadas[:5]
                ) + "."
            )

        return {
            "titulo": ETIQUETA_DOMINIO["equipo"],
            "hechos": "\n".join(lineas),
            "metricas": {
                "pendientes": pendientes.count(),
                "atrasadas": len(atrasadas),
                "por_persona": por_persona,
            },
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_equipo falló", exc_info=True)
        return _vacio("equipo")


# ── Gasto en IA y uso del sistema ────────────────────────────────────


def hechos_ia() -> dict:
    """Cuánto cuestan Los Chalanes y quién los usa."""
    try:
        from lib.analistas.stats import resumen_global

        res = resumen_global(dias=30)
        lineas = [
            f"Gasto en IA de los últimos 30 días: ${res['costo_total']:.2f} USD en "
            f"{res['llamadas_total']} llamadas ({res['tokens_total']:,} tokens).",
        ]
        por_prov = res.get("por_proveedor") or []
        if por_prov:
            lineas.append(
                "Por Chalán: "
                + "; ".join(
                    f"{p.get('apodo') or p.get('provider')} ${p.get('costo_usd', 0):.2f}"
                    for p in por_prov[:5]
                ) + "."
            )
        try:
            from datetime import timedelta

            from apps.el_dictado.models import Dictado
            desde = date.today() - timedelta(days=30)
            dictados = Dictado.objects.filter(creado_en__date__gte=desde)
            total = dictados.count()
            fallidos = dictados.filter(estado__in=("fallo_ia", "aplicado_con_errores")).count()
            if total:
                lineas.append(
                    f"Instrucciones dictadas al Chalán: {total}, de las cuales {fallidos} "
                    f"salieron mal ({fallidos / total * 100:.0f}%)."
                )
        except Exception:  # noqa: BLE001
            pass

        return {
            "titulo": ETIQUETA_DOMINIO["ia"],
            "hechos": "\n".join(lineas),
            "metricas": res,
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_ia falló", exc_info=True)
        return _vacio("ia")


# ── Dispatch ─────────────────────────────────────────────────────────

_FUNCS = {
    "finanzas": hechos_finanzas,
    "cobranza": hechos_cobranza,
    "ventas": hechos_ventas,
    "rentabilidad": hechos_rentabilidad,
    "margenes": hechos_rentabilidad,  # alias histórico
    "perdidos": hechos_perdidos,
    "clientes": hechos_clientes,
    "proveedores": hechos_proveedores,
    "equipo": hechos_equipo,
    "ia": hechos_ia,
}

# Los que necesitan saber QUIÉN pregunta (para respetar privacidad).
_FUNCS_CON_USUARIO = {"equipo"}


def hechos_de(dominio: str, usuario=None) -> dict:
    """Devuelve los hechos de un dominio (o vacío si el dominio no existe)."""
    fn = _FUNCS.get(dominio)
    if not fn:
        return _vacio(dominio)
    if dominio in _FUNCS_CON_USUARIO:
        return fn(usuario)
    return fn()


def todos_los_hechos(usuario=None) -> dict[str, dict]:
    """Todos los dominios — para el digest analítico completo."""
    return {d: hechos_de(d, usuario) for d in DOMINIOS}


def dominios_para(usuario) -> list[str]:
    """Los dominios que esta persona tiene permiso de ver."""
    from lib import permisos

    visibles = []
    for dominio in DOMINIOS:
        check = getattr(permisos, PERMISO_DOMINIO.get(dominio, ""), None)
        if check is None or check(usuario):
            visibles.append(dominio)
    return visibles
