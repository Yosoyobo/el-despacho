"""Exports CSV de La Contaduría para el contador externo.

Formato pólizas planas: una fila por partida (no por asiento). Esto
le permite al contador timbrador alimentar su propio libro fiscal y
reconciliar con CFDI emitidos por su PAC.

Formato catálogo: lista de cuentas activas con tipo, naturaleza y
slot. Útil para que el contador mapee a su catálogo SAT.

UTF-8 BOM + headers español, mismo patrón que `tesoreria/exports.py`.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal

from django.http import HttpResponse

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import CuentaContable, Partida

FORMATOS = ("polizas", "catalogo")

ENCABEZADOS: dict[str, list[str]] = {
    "polizas": [
        "Asiento", "Fecha", "Origen", "Descripción asiento",
        "Código cuenta", "Nombre cuenta", "Tipo", "Naturaleza",
        "Cargo", "Abono", "Descripción partida",
        "Referencia externa", "Anulado", "Capturado por",
    ],
    "catalogo": [
        "Código", "Nombre", "Tipo", "Naturaleza", "Slot",
        "Activa", "Descripción",
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


def _filas_polizas(params):
    desde = params.get("desde") or ""
    hasta = params.get("hasta") or ""
    incluir_anulados = (params.get("incluir_anulados") or "") in ("1", "true", "on")
    origen = (params.get("origen") or "").strip()

    qs = Partida.objects.select_related("asiento", "asiento__creado_por", "cuenta")
    if not incluir_anulados:
        qs = qs.filter(asiento__anulado=False)
    if desde:
        qs = qs.filter(asiento__fecha__gte=desde)
    if hasta:
        qs = qs.filter(asiento__fecha__lte=hasta)
    if origen:
        qs = qs.filter(asiento__origen=origen)

    qs = qs.order_by("asiento__fecha", "asiento__creado_en", "asiento_id", "orden", "pk")
    for p in qs:
        a = p.asiento
        yield [
            a.codigo,
            _fmt_fecha(a.fecha),
            a.get_origen_display() if hasattr(a, "get_origen_display") else a.origen,
            a.descripcion,
            p.cuenta.codigo,
            p.cuenta.nombre,
            p.cuenta.get_tipo_display() if hasattr(p.cuenta, "get_tipo_display") else p.cuenta.tipo,
            p.cuenta.get_naturaleza_display() if hasattr(p.cuenta, "get_naturaleza_display") else p.cuenta.naturaleza,
            _fmt_monto(p.cargo),
            _fmt_monto(p.abono),
            p.descripcion or "",
            a.referencia_externa or "",
            _fmt_bool(a.anulado),
            a.creado_por.email if a.creado_por else "",
        ]


def _filas_catalogo(params):
    incluir_inactivas = (params.get("incluir_inactivas") or "") in ("1", "true", "on")
    qs = CuentaContable.objects.all() if incluir_inactivas else CuentaContable.activas.all()
    for c in qs.order_by("codigo"):
        yield [
            c.codigo,
            c.nombre,
            c.get_tipo_display(),
            c.get_naturaleza_display(),
            c.slot or "",
            _fmt_bool(c.activa),
            c.descripcion or "",
        ]


def filas_para(formato: str, params: dict):
    if formato == "polizas":
        filas = list(_filas_polizas(params))
    elif formato == "catalogo":
        filas = list(_filas_catalogo(params))
    else:
        raise ValueError(f"Formato desconocido: {formato}")
    return ENCABEZADOS[formato], filas


def responder_csv(formato: str, params: dict, *, actor=None):
    encabezados, filas = filas_para(formato, params)
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    nombre = f"contaduria_{formato}_{date.today().isoformat()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{nombre}"'
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(encabezados)
    for f in filas:
        writer.writerow(f)
    emitir(EventoPortavoz(
        tipo="contaduria.exportado",
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload={
            "formato": formato,
            "filas": len(filas),
            "rango": {
                "desde": params.get("desde") or "",
                "hasta": params.get("hasta") or "",
            },
            "incluir_anulados": (params.get("incluir_anulados") or "") in ("1", "true", "on"),
        },
    ))
    return response
