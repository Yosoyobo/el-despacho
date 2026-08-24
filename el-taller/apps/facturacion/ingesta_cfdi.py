"""Recibir un CFDI y ligarlo a su factura — o dejarlo para que alguien decida.

El número que motivó esto, medido el 2026-08-24: **de 36 facturas, sólo 1
tenía su CFDI archivado**. El lugar donde guardarlo existe desde julio; lo que
no ocurre es que alguien lo baje del PAC y lo suba uno por uno.

**La regla del ligado: sólo cuando es inequívoco.** Se busca la factura por
cliente y por monto exacto entre las que aún no tienen comprobante. Si aparece
UNA, se liga sola. Si aparecen dos o ninguna, queda pendiente con el motivo
escrito en español, porque adivinar dejaría la contabilidad apoyada en una
suposición que nadie revisó — y eso es peor que no ligar.

Nada aquí lanza: devuelve un diccionario con lo que pasó. Quien lo llama es un
endpoint que atiende a un robot, y un robot no sabe leer una traza.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

#: Cuánto puede diferir el total del CFDI del de la factura para considerarlos
#: el mismo. Un centavo cubre los redondeos del PAC sin dar por buena una
#: factura que en realidad es de otro monto.
TOLERANCIA = Decimal("0.01")


def _rfc_propio() -> str:
    """El RFC del despacho, de La Bóveda. Vacío si no está configurado."""
    try:
        from ajustes.models.credencial import Credencial

        return (Credencial.obtener("rfc_empresa") or "").strip().upper()
    except Exception as exc:  # noqa: BLE001
        logger.debug("ingesta_cfdi: sin RFC propio configurado: %s", exc)
        return ""


def _candidatas(lectura):
    """Facturas que podrían ser ésta: del mismo cliente, del mismo monto, sin
    comprobante todavía."""
    from apps.facturacion.models import Factura

    qs = (Factura.objects
          .filter(cfdi_uuid="")
          .exclude(estado="cancelada")
          .select_related("cliente"))

    rfc = (lectura.receptor_rfc or "").strip().upper()
    if rfc:
        # El RFC puede vivir en el campo legacy del cliente o en cualquiera de
        # sus razones sociales: se buscan las dos, o una empresa que factura
        # con varios RFC quedaría siempre pendiente.
        from django.db.models import Q
        qs = qs.filter(Q(cliente__rfc__iexact=rfc) | Q(cliente__razones_sociales__rfc__iexact=rfc))

    if lectura.total is None:
        return list(qs.distinct()[:20])

    # El total de una factura es una property (se calcula de sus líneas), así
    # que el filtro por monto se hace en Python. Son pocas filas: sólo las que
    # no tienen comprobante.
    return [f for f in qs.distinct()[:200]
            if abs(_total(f) - lectura.total) <= TOLERANCIA]


def _total(fac) -> Decimal:
    try:
        return Decimal(str(fac.calcular_totales()["total"]))
    except Exception:  # noqa: BLE001
        return Decimal("0")


@transaction.atomic
def recibir(contenido: bytes, *, nombre: str = "cfdi.xml", pdf: bytes | None = None) -> dict:
    """Procesa un CFDI que llegó. Idempotente por folio fiscal.

    Devuelve `{ok, estado, mensaje, uuid, factura}`.
    """
    from lib import cfdi

    from .models import ESTADO_LIGADO, ESTADO_PENDIENTE, CfdiEntrante

    lec = cfdi.leer(contenido)
    if not lec.ok:
        return {"ok": False, "estado": "rechazado", "mensaje": lec.error, "uuid": ""}
    if not lec.uuid:
        return {"ok": False, "estado": "rechazado", "mensaje": lec.error, "uuid": ""}

    # El folio fiscal es único en todo México: es lo que hace que reenviar el
    # mismo correo diez veces no archive diez copias.
    previo = CfdiEntrante.objects.filter(uuid=lec.uuid).first()
    if previo:
        return {
            "ok": True, "estado": previo.estado, "uuid": lec.uuid,
            "mensaje": "Ya se había recibido este comprobante.",
            "factura": getattr(previo.factura, "codigo", ""),
        }

    entrante = CfdiEntrante(
        uuid=lec.uuid,
        emisor_rfc=lec.emisor_rfc, emisor_nombre=lec.emisor_nombre[:200],
        receptor_rfc=lec.receptor_rfc, receptor_nombre=lec.receptor_nombre[:200],
        total=lec.total, moneda=lec.moneda, fecha_cfdi=lec.fecha,
        referencia=lec.referencia[:60],
    )

    propio = _rfc_propio()
    if propio and lec.emisor_rfc and lec.emisor_rfc != propio:
        # Nos lo emitieron a nosotros: es la factura de un proveedor, o sea un
        # gasto. Se archiva pero NO se liga a una Factura, que representa lo
        # que nosotros le cobramos a un cliente. Confundirlos metería una
        # compra en los ingresos.
        entrante.motivo = (
            f"Es una factura que nos emitió {lec.emisor_nombre or lec.emisor_rfc}. "
            "Se archiva como comprobante recibido; el gasto se registra aparte."
        )
        entrante.save()
        _guardar_archivo(entrante, contenido, nombre)
        return {"ok": True, "estado": ESTADO_PENDIENTE, "uuid": lec.uuid,
                "mensaje": entrante.motivo, "factura": ""}

    candidatas = _candidatas(lec)

    if len(candidatas) == 1:
        fac = candidatas[0]
        entrante.factura = fac
        entrante.estado = ESTADO_LIGADO
        entrante.resuelto_en = timezone.now()
        entrante.save()
        _guardar_archivo(entrante, contenido, nombre)
        _ligar_a_factura(fac, contenido, nombre, pdf, lec.uuid)
        return {"ok": True, "estado": ESTADO_LIGADO, "uuid": lec.uuid,
                "mensaje": f"Ligado a {fac.codigo}.", "factura": fac.codigo}

    if not candidatas:
        entrante.motivo = (
            f"No se encontró una factura sin comprobante de {lec.receptor_nombre or 'ese cliente'} "
            f"por {lec.total}. Puede que ya tenga el suyo, o que se haya capturado por otro monto."
        )
    else:
        codigos = ", ".join(f.codigo for f in candidatas[:5])
        entrante.motivo = (
            f"Hay {len(candidatas)} facturas que coinciden ({codigos}). "
            "Ligarlo a ciegas dejaría la contabilidad apoyada en una suposición."
        )
    entrante.save()
    _guardar_archivo(entrante, contenido, nombre)
    return {"ok": True, "estado": ESTADO_PENDIENTE, "uuid": lec.uuid,
            "mensaje": entrante.motivo, "factura": ""}


def _guardar_archivo(entrante, contenido: bytes, nombre: str) -> None:
    """Guarda el XML. Best-effort: perder el archivo no debe perder el registro."""
    try:
        from lib.adjuntos import subir

        res = subir(contenido, nombre=nombre, mime="application/xml", subcarpeta="Facturas")
        if getattr(res, "ok", False):
            entrante.archivo_id = (res.data or {}).get("id", "")
            entrante.save(update_fields=["archivo_id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingesta_cfdi: no se pudo guardar el XML: %s", exc)


def _ligar_a_factura(fac, contenido: bytes, nombre: str, pdf, uuid: str) -> None:
    """Deja el comprobante en la factura por el camino de siempre."""
    try:
        import io

        from . import services

        xml = io.BytesIO(contenido)
        xml.name = nombre
        services.almacenar_cfdi(fac, xml_file=xml, pdf_file=pdf, cfdi_uuid=uuid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingesta_cfdi: no se pudo ligar a %s: %s", fac.codigo, exc)


__all__ = ["TOLERANCIA", "recibir"]
