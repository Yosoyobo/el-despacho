"""El estado de cuenta de un cliente (La Imprenta)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ..esquema import Bloque, Columna, DefinicionTipo
from .base import Documento

#: Cuántos días hacia atrás entran las facturas ya pagadas y los pagos.
DIAS_HISTORIA = 90

ESTADO_CUENTA_DEF = DefinicionTipo(
    slug="estado_cuenta",
    nombre="Estado de cuenta",
    subcarpeta="Estados de cuenta",
    ayuda="Por cliente: lo facturado, lo pagado y lo que debe a hoy. Sirve para la cobranza.",
    bloques=(
        Bloque("fecha", "Fecha de corte (arriba a la izquierda)"),
        Bloque("logo", "Logotipo"),
        Bloque("pagadas", f"Facturas ya pagadas (últimos {DIAS_HISTORIA} días)"),
        Bloque("pagos", f"Pagos recibidos (últimos {DIAS_HISTORIA} días)"),
        Bloque("vencido", "Cuánto está vencido"),
    ),
    columnas=(
        Columna("folio", "Factura"),
        Columna("emision", "Emisión"),
        Columna("vence", "Vence"),
        Columna("total", "Total"),
        Columna("cobrado", "Pagado"),
        Columna("saldo", "Saldo"),
        Columna("rotulo_saldo", "Saldo a la fecha"),
        Columna("rotulo_pagos", "Pagos recibidos"),
    ),
    datos_default=("razon_social", "rfc", "bancarios"),
    qr_opciones=("", "portal"),
)


def _cliente(pk):
    from apps.la_cartera.models import Cliente

    return Cliente.objects.get(pk=pk)


def _puede(usuario, obj=None) -> bool:
    from lib import permisos

    return permisos.puede_ver_facturacion(usuario)


def _contexto(cliente, cfg) -> dict:
    from apps.facturacion.models import Factura
    from apps.tesoreria.models import Ingreso

    hoy = date.today()
    desde = hoy - timedelta(days=DIAS_HISTORIA)
    filas, total_saldo, vencido = [], Decimal("0"), Decimal("0")
    qs = (Factura.objects.filter(cliente=cliente).exclude(estado="cancelada")
          .prefetch_related("items", "impuestos__tasa").order_by("fecha_emision", "pk"))
    for f in qs:
        if not f.facturada_de_verdad:
            continue
        total = f.calcular_totales()["total"]
        saldo = (total - (f.monto_cobrado or Decimal("0"))).quantize(Decimal("0.01"))
        if saldo <= 0 and (not cfg.bloque("pagadas") or f.fecha_emision < desde):
            continue
        es_vencida = saldo > 0 and f.fecha_vencimiento < hoy
        filas.append({"f": f, "total": total, "cobrado": f.monto_cobrado or Decimal("0"),
                      "saldo": saldo, "vencida": es_vencida})
        total_saldo += max(saldo, Decimal("0"))
        if es_vencida:
            vencido += saldo
    pagos = []
    if cfg.bloque("pagos"):
        pagos = list(Ingreso.objects.filter(cliente=cliente, anulado=False, fecha__gte=desde)
                     .select_related("factura").order_by("fecha", "pk"))
    return {"cliente": cliente, "filas": filas, "pagos": pagos, "saldo": total_saldo,
            "vencido": vencido, "corte": hoy, "dias": DIAS_HISTORIA}


def _piezas(cliente) -> dict:
    return {"folio": "", "cliente": cliente.razon_social, "proyecto": "",
            "fecha": date.today().strftime("%Y-%m-%d"), "version": ""}


def _ejemplos(limite: int = 15):
    from apps.facturacion.models import Factura
    from apps.la_cartera.models import Cliente

    ids = list(Factura.objects.exclude(estado="cancelada").order_by("-actualizado_en")
               .values_list("cliente_id", flat=True)[:200])
    vistos = list(dict.fromkeys(ids))[:limite]
    nombres = dict(Cliente.objects.filter(pk__in=vistos).values_list("pk", "razon_social"))
    return [(pk, nombres.get(pk, "—")) for pk in vistos if pk in nombres]


ESTADO_CUENTA = Documento(
    definicion=ESTADO_CUENTA_DEF,
    plantilla="imprenta/documentos/estado_cuenta.html",
    rotulo="Estado de cuenta",
    obtener=_cliente, puede=_puede, contexto=_contexto,
    piezas=_piezas, ejemplos=_ejemplos,
    titulo=lambda c: f"Estado de cuenta · {c.razon_social}",
    fecha=lambda c: date.today(),
)
