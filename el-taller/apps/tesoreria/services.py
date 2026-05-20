"""Servicios y queries de La Tesorería.

Concentra la lógica que reúsan vistas, exports y el ejecutor de El Dictado.
Mantener consultas en un solo lugar — un cambio de modelo no debe arrastrar
4 vistas para reconciliarse."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, Sum
from django.utils import timezone

from .models import Egreso, Ingreso


def cuentas_por_pagar_qs():
    """Egresos no anulados con estado distinto de pagado."""
    return Egreso.vigentes.exclude(estado_pago="pagado")


def cxc_proyectos():
    """Versión simple y legible — proyectos con saldo > 0."""
    from apps.los_proyectos.models import Proyecto
    proyectos = []
    for p in Proyecto.objects.exclude(estado="cancelado"):
        saldo = (p.monto_facturado or 0) - (p.monto_cobrado or 0)
        if saldo > 0:
            proyectos.append((p, saldo))
    proyectos.sort(key=lambda t: t[1], reverse=True)
    return proyectos


def reembolsos_pendientes():
    """Egresos por_reembolsar agrupados por empleado."""
    qs = (
        Egreso.vigentes.filter(estado_pago="por_reembolsar", pagado_por__isnull=False)
        .values("pagado_por", "pagado_por__email", "pagado_por__nombre_completo")
        .annotate(total=Sum("monto"), num=Count("id"))
        .order_by("-total")
    )
    return list(qs)


def charts_landing() -> dict[str, str]:
    """Series JSON para charts de la landing: area mensual (ingresos vs
    egresos últimos 6 meses) + donut top 5 centros de costo (egresos mes)."""
    from lib.graficas import area_mensual, donut_desde_conteo
    hoy = date.today()
    y, m = hoy.year, hoy.month
    anchors = []
    for _ in range(6):
        anchors.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    anchors.reverse()
    labels, ing_data, egr_data, util_data = [], [], [], []
    for yy, mm in anchors:
        labels.append(date(yy, mm, 1).strftime("%b"))
        ing = Ingreso.vigentes.filter(fecha__year=yy, fecha__month=mm).aggregate(t=Sum("monto"))["t"] or Decimal("0")
        egr = Egreso.vigentes.filter(fecha__year=yy, fecha__month=mm).aggregate(t=Sum("monto"))["t"] or Decimal("0")
        ing_data.append(ing)
        egr_data.append(egr)
        util_data.append(ing - egr)
    inicio_mes = hoy.replace(day=1)
    centros = (
        Egreso.vigentes.filter(fecha__gte=inicio_mes)
        .values("centro_de_costo__nombre")
        .annotate(total=Sum("monto"))
        .order_by("-total")[:5]
    )
    conteo_centros = {(c["centro_de_costo__nombre"] or "Sin centro"): c["total"] for c in centros}
    return {
        "area_flujo": area_mensual(labels, [
            {"name": "Ingresos", "data": ing_data, "color": "#12b76a"},
            {"name": "Egresos", "data": egr_data, "color": "#f04438"},
            {"name": "Utilidad", "data": util_data, "color": "#465fff"},
        ]),
        "donut_centros": donut_desde_conteo(conteo_centros),
    }


def kpis_landing(usuario) -> dict[str, Any]:
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    ingresos_mes = Ingreso.vigentes.filter(fecha__gte=inicio_mes).aggregate(
        s=Sum("monto"))["s"] or Decimal("0")
    egresos_mes = Egreso.vigentes.filter(fecha__gte=inicio_mes).aggregate(
        s=Sum("monto"))["s"] or Decimal("0")
    cxp_total = cuentas_por_pagar_qs().aggregate(s=Sum("monto"))["s"] or Decimal("0")
    cxp_num = cuentas_por_pagar_qs().count()
    reembolsos_total = (
        Egreso.vigentes.filter(estado_pago="por_reembolsar").aggregate(
            s=Sum("monto"))["s"] or Decimal("0")
    )
    return {
        "ingresos_mes": ingresos_mes,
        "egresos_mes": egresos_mes,
        "utilidad_mes": ingresos_mes - egresos_mes,
        "cxp_total": cxp_total,
        "cxp_num": cxp_num,
        "reembolsos_total": reembolsos_total,
    }


def reporte_mes(anio: int, mes: int) -> dict[str, Any]:
    desde = date(anio, mes, 1)
    hasta = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)
    ingresos = Ingreso.vigentes.filter(fecha__gte=desde, fecha__lt=hasta)
    egresos = Egreso.vigentes.filter(fecha__gte=desde, fecha__lt=hasta)
    por_centro = (
        egresos.values("centro_de_costo__nombre")
        .annotate(total=Sum("monto"), num=Count("id"))
        .order_by("-total")
    )
    top_proveedores = (
        egresos.exclude(proveedor_nombre="")
        .values("proveedor_nombre")
        .annotate(total=Sum("monto"))
        .order_by("-total")[:10]
    )
    por_cliente = (
        ingresos.filter(cliente__isnull=False)
        .values("cliente__razon_social")
        .annotate(total=Sum("monto"))
        .order_by("-total")[:10]
    )
    return {
        "desde": desde,
        "hasta": hasta,
        "ingresos_total": ingresos.aggregate(s=Sum("monto"))["s"] or Decimal("0"),
        "egresos_total": egresos.aggregate(s=Sum("monto"))["s"] or Decimal("0"),
        "por_centro": list(por_centro),
        "top_proveedores": list(top_proveedores),
        "por_cliente": list(por_cliente),
    }


def anular_ingreso(ingreso: Ingreso, usuario, motivo: str) -> Ingreso:
    if ingreso.anulado:
        return ingreso
    ingreso.anulado = True
    ingreso.anulado_por = usuario
    ingreso.anulado_en = timezone.now()
    ingreso.motivo_anulacion = (motivo or "").strip()[:300]
    ingreso.save(update_fields=["anulado", "anulado_por", "anulado_en",
                                 "motivo_anulacion", "actualizado_en"])
    return ingreso


def anular_egreso(egreso: Egreso, usuario, motivo: str) -> Egreso:
    if egreso.anulado:
        return egreso
    egreso.anulado = True
    egreso.anulado_por = usuario
    egreso.anulado_en = timezone.now()
    egreso.motivo_anulacion = (motivo or "").strip()[:300]
    egreso.save(update_fields=["anulado", "anulado_por", "anulado_en",
                                "motivo_anulacion", "actualizado_en"])
    return egreso
