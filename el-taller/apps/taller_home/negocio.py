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

Dominios: finanzas · cobranza · ventas · margenes (Catálogo — "inventario" en
este despacho de servicios es análisis de costos/márgenes, no stock).
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)

DOMINIOS = ("finanzas", "cobranza", "ventas", "margenes")
ETIQUETA_DOMINIO = {
    "finanzas": "Económicos / Finanzas",
    "cobranza": "Cobranza (CxC)",
    "ventas": "Ventas y pipeline",
    "margenes": "Costos y márgenes del Catálogo",
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
    """Conversión de cotizaciones + pipeline de proyectos + facturado del mes."""
    try:
        from apps.cotizaciones import services as cot_services
        from apps.facturacion import services as fac_services
        from apps.los_proyectos.models import Proyecto

        cot = cot_services.kpis_landing()
        fac = fac_services.kpis_landing()

        # Pipeline de proyectos por estado (no cancelados).
        pipeline: dict[str, int] = {}
        for p in Proyecto.objects.exclude(estado="cancelado").values("estado"):
            pipeline[p["estado"]] = pipeline.get(p["estado"], 0) + 1

        # Conversión aproximada: aprobadas / (enviadas + aprobadas).
        base = cot["enviadas"] + cot["aprobadas"]
        conversion = (cot["aprobadas"] / base * 100) if base else 0.0

        lineas = [
            f"Cotizaciones: {cot['borradores']} en borrador, {cot['enviadas']} enviadas, "
            f"{cot['aprobadas']} aprobadas, {cot['vencidas']} vencidas.",
            f"Conversión aprox (aprobadas/(enviadas+aprobadas)): {conversion:.0f}%.",
            f"Anticipos por facturar: {cot.get('anticipos_pendientes', 0)}.",
            "Pipeline de proyectos por estado: "
            + (", ".join(f"{e}={n}" for e, n in sorted(pipeline.items())) or "vacío") + ".",
            f"Facturas cobradas este mes: {fac['cobradas_mes']}.",
        ]
        return {
            "titulo": ETIQUETA_DOMINIO["ventas"],
            "hechos": "\n".join(lineas),
            "metricas": {
                "cotizaciones": cot, "conversion_pct": round(conversion, 1),
                "pipeline": pipeline, "cobradas_mes": fac["cobradas_mes"],
            },
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_ventas falló", exc_info=True)
        return _vacio("ventas")


# ── Costos y márgenes del Catálogo ───────────────────────────────────


def hechos_margenes() -> dict:
    """Márgenes de los productos/servicios del Catálogo (no hay stock real)."""
    try:
        from apps.el_catalogo.models import Servicio

        servicios = list(Servicio.activos.all())
        if not servicios:
            return _vacio("margenes")

        con_costo = [s for s in servicios if s.costo and s.costo > 0]
        sin_costo = [s for s in servicios if not s.costo or s.costo <= 0]
        margenes = [(s.nombre, s.margen_porcentaje, float(s.precio_base or 0), float(s.costo or 0))
                    for s in con_costo]
        margenes.sort(key=lambda t: t[1])  # ascendente: peores márgenes primero
        peores = margenes[:5]
        prom = (sum(m[1] for m in margenes) / len(margenes)) if margenes else 0.0

        lineas = [
            f"Productos/servicios activos: {len(servicios)} "
            f"({len(con_costo)} con costo capturado, {len(sin_costo)} sin costo).",
            f"Margen promedio (con costo): {prom:.1f}%.",
            "Márgenes más bajos: "
            + ("; ".join(f"{n} {m:.0f}% (precio {_money(p)}, costo {_money(c)})"
                         for n, m, p, c in peores) or "ninguno") + ".",
        ]
        if sin_costo:
            lineas.append(
                "Sin costo capturado (margen no calculable): "
                + ", ".join(s.nombre for s in sin_costo[:8])
                + ("…" if len(sin_costo) > 8 else "") + ".")
        return {
            "titulo": ETIQUETA_DOMINIO["margenes"],
            "hechos": "\n".join(lineas),
            "metricas": {
                "total_servicios": len(servicios), "con_costo": len(con_costo),
                "sin_costo": len(sin_costo), "margen_promedio": round(prom, 1),
                "peores_margenes": [
                    {"nombre": n, "margen_pct": round(m, 1), "precio": p, "costo": c}
                    for n, m, p, c in peores
                ],
            },
        }
    except Exception:  # noqa: BLE001
        logger.warning("hechos_margenes falló", exc_info=True)
        return _vacio("margenes")


# ── Dispatch ─────────────────────────────────────────────────────────

_FUNCS = {
    "finanzas": hechos_finanzas,
    "cobranza": hechos_cobranza,
    "ventas": hechos_ventas,
    "margenes": hechos_margenes,
}


def hechos_de(dominio: str) -> dict:
    """Devuelve los hechos de un dominio (o vacío si el dominio no existe)."""
    fn = _FUNCS.get(dominio)
    return fn() if fn else _vacio(dominio)


def todos_los_hechos() -> dict[str, dict]:
    """Todos los dominios — para el digest analítico completo."""
    return {d: hechos_de(d) for d in DOMINIOS}
