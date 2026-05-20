"""CSV exports (DOC_06 §8.2). Sheets export se enchufa en S2b.3b cuando
el wrapper de Google Sheets exista.

- UTF-8 con BOM para que Excel abra acentos sin reconfigurar.
- Fechas ISO 8601 (YYYY-MM-DD).
- Montos con punto decimal (1234.56), nunca formato regional.
- Booleanos como Sí / No.
- Encabezados localizados en español.
- Centro de costo como nombre legible. Proyecto/cliente como código/razón social.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.http import HttpResponse

from .models import Egreso, Ingreso

VISTAS = ("ingresos", "egresos", "cxc", "cxp", "reembolsos", "movimientos")

ENCABEZADOS: dict[str, list[str]] = {
    "ingresos": [
        "Código", "Fecha", "Monto", "Moneda", "Descripción", "Cliente",
        "Proyecto", "Método", "Referencia externa", "Capturado por",
        "Anulado", "Motivo anulación",
    ],
    "egresos": [
        "Código", "Fecha", "Monto", "Moneda", "Descripción", "Proveedor",
        "Centro de costo", "Proyecto", "Pagado por", "Solicitado por",
        "Estado de pago", "Método", "Origen", "Tiene comprobante",
        "Enlace comprobante", "Capturado por", "Anulado",
    ],
    "cxc": [
        "Proyecto", "Cliente", "Monto facturado", "Monto cobrado",
        "Saldo pendiente", "Fecha ingreso esperado",
    ],
    "cxp": [
        "Código", "Fecha", "Proveedor", "Monto", "Pagado por",
        "Estado de pago", "Días desde captura",
    ],
    "reembolsos": [
        "Empleado", "Email", "Total pendiente", "Núm. gastos",
    ],
    "movimientos": [
        "Tipo", "Código", "Fecha", "Monto", "Descripción",
        "Cliente o proveedor", "Proyecto", "Centro de costo",
    ],
}


def _fmt_monto(v) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return f"{v:.2f}"
    return f"{Decimal(str(v)):.2f}"


def _fmt_fecha(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, datetime):
        v = v.date()
    return v.isoformat() if isinstance(v, date) else str(v)


def _fmt_bool(v) -> str:
    return "Sí" if v else "No"


def _aplicar_filtros_ingresos(qs, params):
    desde = params.get("desde") or ""
    hasta = params.get("hasta") or ""
    cliente_id = params.get("cliente") or ""
    proyecto_id = params.get("proyecto") or ""
    metodo = params.get("metodo") or ""
    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)
    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)
    if proyecto_id:
        qs = qs.filter(proyecto_id=proyecto_id)
    if metodo:
        qs = qs.filter(metodo=metodo)
    return qs


def _aplicar_filtros_egresos(qs, params):
    desde = params.get("desde") or ""
    hasta = params.get("hasta") or ""
    centro = params.get("centro") or ""
    proyecto_id = params.get("proyecto") or ""
    estado = params.get("estado_pago") or ""
    pagado_por = params.get("pagado_por") or ""
    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)
    if centro:
        qs = qs.filter(centro_de_costo__slug=centro)
    if proyecto_id:
        qs = qs.filter(proyecto_id=proyecto_id)
    if estado:
        qs = qs.filter(estado_pago=estado)
    if pagado_por:
        qs = qs.filter(pagado_por_id=pagado_por)
    return qs


def _filas_ingresos(qs):
    for i in qs.select_related("cliente", "proyecto", "creado_por"):
        yield [
            i.codigo,
            _fmt_fecha(i.fecha),
            _fmt_monto(i.monto),
            i.moneda,
            i.descripcion,
            i.cliente.razon_social if i.cliente else "",
            i.proyecto.codigo if i.proyecto else "",
            i.get_metodo_display(),
            i.referencia_externa,
            i.creado_por.email if i.creado_por else "",
            _fmt_bool(i.anulado),
            i.motivo_anulacion,
        ]


def _filas_egresos(qs):
    for e in qs.select_related("centro_de_costo", "proyecto", "pagado_por",
                                "solicitado_por", "creado_por"):
        yield [
            e.codigo,
            _fmt_fecha(e.fecha),
            _fmt_monto(e.monto),
            e.moneda,
            e.descripcion,
            e.proveedor_nombre,
            e.centro_de_costo.nombre,
            e.proyecto.codigo if e.proyecto else "",
            e.pagado_por.email if e.pagado_por else "",
            e.solicitado_por.email if e.solicitado_por else "",
            e.get_estado_pago_display(),
            e.get_metodo_display(),
            e.get_origen_display(),
            _fmt_bool(e.tiene_comprobante),
            e.drive_url_view,
            e.creado_por.email if e.creado_por else "",
            _fmt_bool(e.anulado),
        ]


def _filas_cxc():
    from .services import cxc_proyectos
    for p, saldo in cxc_proyectos():
        yield [
            p.codigo,
            p.cliente.razon_social if p.cliente else "",
            _fmt_monto(p.monto_facturado),
            _fmt_monto(p.monto_cobrado),
            _fmt_monto(saldo),
            _fmt_fecha(p.fecha_ingreso_esperado),
        ]


def _filas_cxp(qs):
    from datetime import date as _d
    hoy = _d.today()
    for e in qs.select_related("pagado_por"):
        dias = (hoy - e.creado_en.date()).days if e.creado_en else 0
        yield [
            e.codigo,
            _fmt_fecha(e.fecha),
            e.proveedor_nombre,
            _fmt_monto(e.monto),
            e.pagado_por.email if e.pagado_por else "",
            e.get_estado_pago_display(),
            str(dias),
        ]


def _filas_reembolsos():
    from .services import reembolsos_pendientes
    for r in reembolsos_pendientes():
        yield [
            r.get("pagado_por__nombre_completo") or "",
            r.get("pagado_por__email") or "",
            _fmt_monto(r["total"]),
            str(r["num"]),
        ]


def _filas_movimientos(params):
    qs_i = _aplicar_filtros_ingresos(Ingreso.vigentes.all(), params)
    qs_e = _aplicar_filtros_egresos(Egreso.vigentes.all(), params)
    movimientos = []
    for i in qs_i.select_related("cliente", "proyecto"):
        movimientos.append((
            i.fecha, "Ingreso", i.codigo, i.monto, i.descripcion,
            i.cliente.razon_social if i.cliente else "",
            i.proyecto.codigo if i.proyecto else "",
            "",
        ))
    for e in qs_e.select_related("centro_de_costo", "proyecto"):
        movimientos.append((
            e.fecha, "Egreso", e.codigo, e.monto, e.descripcion,
            e.proveedor_nombre,
            e.proyecto.codigo if e.proyecto else "",
            e.centro_de_costo.nombre,
        ))
    movimientos.sort(key=lambda t: t[0] or date.min, reverse=True)
    for fecha, tipo, codigo, monto, desc, cli_o_prov, proyecto, centro in movimientos:
        yield [
            tipo, codigo, _fmt_fecha(fecha), _fmt_monto(monto),
            desc, cli_o_prov, proyecto, centro,
        ]


def filas_para(vista: str, params: dict) -> tuple[list[str], list[list[Any]]]:
    if vista == "ingresos":
        qs = _aplicar_filtros_ingresos(Ingreso.vigentes.all(), params)
        filas = list(_filas_ingresos(qs))
    elif vista == "egresos":
        qs = _aplicar_filtros_egresos(Egreso.vigentes.all(), params)
        filas = list(_filas_egresos(qs))
    elif vista == "cxc":
        filas = list(_filas_cxc())
    elif vista == "cxp":
        estado = params.get("estado_pago") or ""
        qs = Egreso.vigentes.exclude(estado_pago="pagado")
        if estado:
            qs = qs.filter(estado_pago=estado)
        filas = list(_filas_cxp(qs))
    elif vista == "reembolsos":
        filas = list(_filas_reembolsos())
    elif vista == "movimientos":
        filas = list(_filas_movimientos(params))
    else:
        raise ValueError(f"Vista desconocida: {vista}")
    return ENCABEZADOS[vista], filas


def responder_csv(vista: str, params: dict) -> HttpResponse:
    encabezados, filas = filas_para(vista, params)
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    nombre = f"tesoreria_{vista}_{date.today().isoformat()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{nombre}"'
    # BOM para Excel
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(encabezados)
    for f in filas:
        writer.writerow(f)
    return response, len(filas)
