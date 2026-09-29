"""Lecturas de La Caja para El Chalán (links de pago y pagos en línea).

Van aparte de `lecturas.py` para no inflarlo; se registran en el mismo
registro único. Gating `caja` → `caja.ver` (§4 #20). Sólo leen.
"""

from __future__ import annotations

from .registro import Capacidad, registrar

_LIMITE = 10


def _limite(args: dict) -> int:
    try:
        return max(1, min(int(args.get("limite") or _LIMITE), 30))
    except (TypeError, ValueError):
        return _LIMITE


def _h_links_de_pago(args: dict, usuario) -> dict:
    from apps.caja.models import LinkPago
    from apps.caja.services import configurada, resumen

    qs = LinkPago.objects.select_related("cliente", "factura", "cotizacion")
    if estado := args.get("estado"):
        qs = qs.filter(estado=estado)
    filas = []
    for link in qs[:_limite(args)]:
        filas.append({
            "id": link.pk,
            "que": link.referencia,
            "cliente": getattr(link.cliente, "razon_social", ""),
            "monto": float(link.monto),
            "estado": link.get_estado_display(),
            "vence": link.vence_en.date().isoformat() if link.vence_en else "",
            # El link sólo sirve mientras está vigente; uno muerto no se ofrece.
            "url": link.url_publica() if link.cobrable else "",
        })
    r = resumen()
    return {
        "caja_encendida": configurada(),
        "links_vigentes": r["links_vigentes"],
        "por_cobrar_en_links": float(r["por_cobrar_links"]),
        "links": filas,
    }


def _h_pagos_recientes(args: dict, usuario) -> dict:
    from apps.caja.models import PagoRecibido
    from apps.caja.services import resumen

    qs = PagoRecibido.objects.select_related("link", "link__cliente", "ingreso")
    if estado := args.get("estado"):
        qs = qs.filter(estado=estado)
    filas = []
    for p in qs[:_limite(args)]:
        filas.append({
            "fecha": p.fecha_pago.date().isoformat() if p.fecha_pago else "",
            "cliente": getattr(getattr(p.link, "cliente", None), "razon_social", ""),
            "que": p.link.referencia if p.link else "",
            "monto": float(p.monto),
            "pasarela": p.get_pasarela_display(),
            "estado": p.get_estado_display(),
            "motivo": p.motivo,
            "ingreso": getattr(p.ingreso, "codigo", ""),
        })
    r = resumen()
    return {
        "cobrado_en_linea_este_mes": float(r["cobrado_mes"]),
        "pagos_este_mes": r["pagos_mes"],
        "por_revisar": r["por_revisar"],
        "por_acreditar": r["pendientes"],
        "pagos": filas,
    }


_LECTURAS = {
    "links_de_pago": Capacidad(
        nombre="links_de_pago",
        descripcion=(
            "Los links de pago en línea de La Caja (Stripe / MercadoPago): de qué "
            "factura, anticipo o monto libre son, de qué cliente, por cuánto, si "
            "siguen vigentes y su URL para mandarla al cliente. Args: estado "
            "(opcional: vigente|pagado|anulado|vencido), limite (opcional)."
        ),
        args_schema={"estado": {"tipo": "str", "requerido": False,
                                "enum": ["vigente", "pagado", "anulado", "vencido"]},
                     "limite": {"tipo": "int", "requerido": False}},
        gating="caja", fn=_h_links_de_pago,
    ),
    "pagos_recientes": Capacidad(
        nombre="pagos_recientes",
        descripcion=(
            "Los pagos que llegaron en línea por Stripe o MercadoPago: cuánto, de "
            "quién, si ya se registraron solos o quedaron por revisar (y por qué), "
            "y lo cobrado en línea este mes. Args: estado (opcional: registrado|"
            "por_revisar|pendiente|rechazado|descartado), limite (opcional)."
        ),
        args_schema={"estado": {"tipo": "str", "requerido": False,
                                "enum": ["registrado", "por_revisar", "pendiente", "rechazado", "descartado"]},
                     "limite": {"tipo": "int", "requerido": False}},
        gating="caja", fn=_h_pagos_recientes,
    ),
}

for _cap in _LECTURAS.values():
    registrar(_cap)
