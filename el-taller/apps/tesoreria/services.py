"""Servicios y queries de La Tesorería.

Concentra la lógica que reúsan vistas, exports y el ejecutor de El Dictado.
Mantener consultas en un solo lugar — un cambio de modelo no debe arrastrar
4 vistas para reconciliarse."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
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


def cxc_unificado():
    """CxC unificado: facturas emitidas (con saldo) + anticipos pendientes
    + proyectos legacy con saldo.

    Retorna lista de dicts ordenada por vencimiento ascendente, formato:

        {
            "tipo": "factura" | "anticipo" | "proyecto",
            "codigo": "FAC-2026-0001" | "COT-2026-0001" | "PRY-000123",
            "cliente": "...",
            "cliente_id": int | None,
            "proyecto_codigo": "PRY-000123" | "",
            "monto_total": Decimal,
            "monto_cobrado": Decimal,
            "saldo": Decimal,
            "fecha_emision": date | None,
            "fecha_vencimiento": date | None,
            "url_detalle": "/facturacion/N/" | "/cotizaciones/N/" | "/proyectos/N/",
            "estado_visible": "vencida" | "emitida" | "cobrada_parcial" | "pendiente",
        }

    Evita doble conteo: un proyecto con factura emitida vinculada NO se
    cuenta como CxC legacy (sólo la factura cuenta).
    """
    from datetime import date as _date

    from apps.facturacion.models import Factura
    from apps.los_proyectos.models import Proyecto
    try:
        from apps.cotizaciones.services import cotizaciones_con_anticipo_pendiente
    except Exception:
        def cotizaciones_con_anticipo_pendiente():
            return []

    filas = []
    hoy = _date.today()

    # 1. Facturas con saldo pendiente
    proyectos_con_factura: set[int] = set()
    facturas_qs = (
        Factura.vigentes.exclude(estado="cancelada")
        .filter(estado__in=["emitida", "cobrada_parcial"])
        .select_related("cliente", "proyecto")
        .order_by("fecha_vencimiento")
    )
    for fac in facturas_qs:
        saldo = fac.saldo_pendiente
        if saldo <= 0:
            continue
        if fac.proyecto_id:
            proyectos_con_factura.add(fac.proyecto_id)
        estado_vis = "vencida" if (fac.fecha_vencimiento and fac.fecha_vencimiento < hoy) else fac.estado
        totales = fac.calcular_totales()
        filas.append({
            "tipo": "factura",
            "codigo": fac.codigo,
            "cliente": fac.cliente.razon_social if fac.cliente else "—",
            "cliente_id": fac.cliente_id,
            "proyecto_codigo": fac.proyecto.codigo if fac.proyecto else "",
            "monto_total": Decimal(totales["total"]),
            "monto_cobrado": Decimal(fac.monto_cobrado or 0),
            "saldo": saldo,
            "fecha_emision": fac.fecha_emision,
            "fecha_vencimiento": fac.fecha_vencimiento,
            "url_detalle": f"/facturacion/{fac.pk}/",
            "estado_visible": estado_vis,
        })

    # 2. Anticipos pendientes de cotizaciones aprobadas
    for cot in cotizaciones_con_anticipo_pendiente():
        saldo = cot.anticipo_monto
        if saldo <= 0:
            continue
        filas.append({
            "tipo": "anticipo",
            "codigo": cot.codigo,
            "cliente": cot.cliente.razon_social if cot.cliente else "—",
            "cliente_id": cot.cliente_id,
            "proyecto_codigo": cot.proyecto.codigo if cot.proyecto else "",
            "monto_total": saldo,
            "monto_cobrado": Decimal("0.00"),
            "saldo": saldo,
            "fecha_emision": cot.aprobada_en.date() if cot.aprobada_en else cot.fecha_emision,
            "fecha_vencimiento": cot.fecha_validez,
            "url_detalle": f"/cotizaciones/{cot.pk}/",
            "estado_visible": "anticipo_pendiente",
        })

    # 3. Proyectos legacy con saldo (excluyendo los que ya tienen factura)
    for p in Proyecto.objects.exclude(estado="cancelado"):
        if p.pk in proyectos_con_factura:
            continue
        saldo = (p.monto_facturado or Decimal("0")) - (p.monto_cobrado or Decimal("0"))
        if saldo <= 0:
            continue
        filas.append({
            "tipo": "proyecto",
            "codigo": p.codigo,
            "cliente": p.cliente.razon_social if p.cliente else "—",
            "cliente_id": p.cliente_id if p.cliente else None,
            "proyecto_codigo": p.codigo,
            "monto_total": Decimal(p.monto_facturado or 0),
            "monto_cobrado": Decimal(p.monto_cobrado or 0),
            "saldo": saldo,
            "fecha_emision": None,
            "fecha_vencimiento": p.fecha_ingreso_esperado if hasattr(p, "fecha_ingreso_esperado") else None,
            "url_detalle": f"/proyectos/{p.pk}/",
            "estado_visible": "proyecto_legacy",
        })

    # Ordenar por fecha de vencimiento ascendente (nulls al final)
    filas.sort(key=lambda f: (f["fecha_vencimiento"] is None, f["fecha_vencimiento"] or _date.max))
    return filas


def cxc_total_unificado() -> Decimal:
    """Suma del saldo de CxC unificado. Usado por KPIs y header."""
    return sum((f["saldo"] for f in cxc_unificado()), Decimal("0"))


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


def series_diarias_30d() -> dict[str, list]:
    """Series de los últimos 30 días (incluyendo hoy) para sparklines.

    Devuelve listas de 30 floats — ingresos diarios, egresos diarios y
    utilidad diaria (ingresos - egresos). Día 0 = hace 29 días; último = hoy.
    """
    from collections import defaultdict
    hoy = date.today()
    desde = hoy - timedelta(days=29)
    ing_por_dia: dict = defaultdict(lambda: Decimal("0"))
    egr_por_dia: dict = defaultdict(lambda: Decimal("0"))
    for fila in Ingreso.vigentes.filter(fecha__gte=desde).values("fecha").annotate(t=Sum("monto")):
        ing_por_dia[fila["fecha"]] = fila["t"] or Decimal("0")
    for fila in Egreso.vigentes.filter(fecha__gte=desde).values("fecha").annotate(t=Sum("monto")):
        egr_por_dia[fila["fecha"]] = fila["t"] or Decimal("0")
    ingresos: list[float] = []
    egresos: list[float] = []
    utilidad: list[float] = []
    for i in range(30):
        d = desde + timedelta(days=i)
        ing = float(ing_por_dia.get(d, 0))
        egr = float(egr_por_dia.get(d, 0))
        ingresos.append(ing)
        egresos.append(egr)
        utilidad.append(ing - egr)
    return {"ingresos": ingresos, "egresos": egresos, "utilidad": utilidad}


def series_mensuales_6m() -> dict[str, list[float]]:
    """Series mensuales de los últimos 6 meses (incluyendo el mes en curso).

    Devuelve listas de 6 floats — ingresos, egresos y utilidad por mes.
    Pensado para los sparklines de las KPI financieras del Dashboard
    (la nota de LC pide "este número en los últimos 6 meses").
    """
    hoy = date.today()
    y, m = hoy.year, hoy.month
    anchors: list[tuple[int, int]] = []
    for _ in range(6):
        anchors.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    anchors.reverse()
    ingresos: list[float] = []
    egresos: list[float] = []
    utilidad: list[float] = []
    for yy, mm in anchors:
        ing = Ingreso.vigentes.filter(fecha__year=yy, fecha__month=mm).aggregate(t=Sum("monto"))["t"] or Decimal("0")
        egr = Egreso.vigentes.filter(fecha__year=yy, fecha__month=mm).aggregate(t=Sum("monto"))["t"] or Decimal("0")
        ingresos.append(float(ing))
        egresos.append(float(egr))
        utilidad.append(float(ing - egr))
    return {"ingresos": ingresos, "egresos": egresos, "utilidad": utilidad}


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
    # Saldos en procesadores de pago (S-Finanzas-V2 #C). Si las cuentas
    # no existen (catálogo viejo), devuelve 0 — el atajo UI sólo se
    # muestra si hay saldo > 0.
    saldo_stripe = Decimal("0")
    saldo_mp = Decimal("0")
    try:
        from apps.contaduria.services import cuenta_por_slot, saldo_cuenta
        c = cuenta_por_slot("stripe_saldo")
        if c is not None:
            saldo_stripe = saldo_cuenta(c)
        c = cuenta_por_slot("mp_saldo")
        if c is not None:
            saldo_mp = saldo_cuenta(c)
    except Exception:
        # Si contaduria no está disponible (poco probable), seguir sin caer.
        pass

    return {
        "ingresos_mes": ingresos_mes,
        "egresos_mes": egresos_mes,
        "utilidad_mes": ingresos_mes - egresos_mes,
        "cxp_total": cxp_total,
        "cxp_num": cxp_num,
        "reembolsos_total": reembolsos_total,
        "saldo_stripe": saldo_stripe,
        "saldo_mp": saldo_mp,
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


def reembolsar_egreso(egreso: Egreso, *, metodo: str, banco_o_caja: str,
                      fecha=None, actor=None) -> Egreso:
    """Marca un Egreso 'por_reembolsar' como pagado y genera asiento
    'D Reembolsos por pagar / H Banco|Caja' en La Contaduría.

    - `banco_o_caja` ∈ {'banco', 'caja'} — slot de la cuenta destino.
    - `metodo`: clave de METODOS_EGRESO (transferencia, efectivo, etc.).
    - Idempotente vía referencia_externa `tesoreria.egreso.reembolso:<pk>`.
    - Valida estado_pago == 'por_reembolsar' y no anulado.
    - Emite evento Portavoz `tesoreria.reembolso_pagado`.
    """
    from apps.contaduria.services import (
        AsientoInvalido,
        crear_asiento,
        cuenta_por_slot,
    )

    if egreso.anulado:
        raise ValueError("No se puede reembolsar un egreso anulado.")
    if egreso.estado_pago != "por_reembolsar":
        raise ValueError(
            f"El egreso {egreso.codigo} no está en estado 'por reembolsar' "
            f"(actual: {egreso.estado_pago})."
        )
    if banco_o_caja not in ("banco", "caja"):
        raise ValueError("banco_o_caja debe ser 'banco' o 'caja'.")

    fecha = fecha or date.today()

    asiento_creado = False
    motivo_no_asiento = ""

    with transaction.atomic():
        egreso.estado_pago = "pagado"
        egreso.metodo = metodo
        egreso.pagado_en = fecha
        egreso.pagado_desde = banco_o_caja
        egreso.save(update_fields=[
            "estado_pago", "metodo", "pagado_en", "pagado_desde", "actualizado_en",
        ])

        reembolsos = cuenta_por_slot("reembolsos")
        destino = cuenta_por_slot(banco_o_caja)
        if reembolsos is None:
            motivo_no_asiento = "Catálogo incompleto: falta cuenta con slot 'reembolsos'."
        elif destino is None:
            motivo_no_asiento = f"Catálogo incompleto: falta cuenta con slot '{banco_o_caja}'."
        else:
            empleado_email = egreso.pagado_por.email if egreso.pagado_por else "—"
            try:
                crear_asiento(
                    descripcion=f"Reembolso a {empleado_email} · {egreso.codigo}",
                    fecha=fecha,
                    origen="auto_reembolso",
                    referencia_externa=f"tesoreria.egreso.reembolso:{egreso.pk}",
                    creado_por=actor,
                    partidas=[
                        {"cuenta": reembolsos, "cargo": egreso.monto, "orden": 0,
                         "descripcion": f"Cancela reembolso por pagar de {empleado_email}"},
                        {"cuenta": destino, "abono": egreso.monto, "orden": 1,
                         "descripcion": f"{metodo} desde {banco_o_caja}"},
                    ],
                    idempotente=True,
                )
                asiento_creado = True
            except AsientoInvalido as e:
                # No tumbamos la transacción de Tesorería por un fallo contable.
                motivo_no_asiento = f"Asiento inválido: {e}"

    from lib.portavoz import emitir
    from lib.portavoz_eventos import EventoPortavoz
    tipo_evento = (
        "tesoreria.reembolso_pagado" if asiento_creado
        else "tesoreria.reembolso_sin_asiento"
    )
    emitir(EventoPortavoz(
        tipo=tipo_evento,
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload={
            "egreso_id": egreso.pk,
            "codigo": egreso.codigo,
            "monto": float(egreso.monto),
            "metodo": metodo,
            "banco_o_caja": banco_o_caja,
            "empleado_email": egreso.pagado_por.email if egreso.pagado_por else None,
            "asiento_creado": asiento_creado,
            "motivo_no_asiento": motivo_no_asiento,
        },
    ))
    # Anotamos el resultado en el egreso para que la vista lo surfacee.
    egreso._reembolso_asiento_creado = asiento_creado
    egreso._reembolso_motivo_no_asiento = motivo_no_asiento
    return egreso


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
