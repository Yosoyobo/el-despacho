"""Señales de La Caja.

Cuando una factura cambia (alguien registró un cobro a mano, se canceló, se
cobró completa), sus links vigentes que ya no cuadran con el saldo se anulan
AL MOMENTO. Así el link que el cliente tiene en su correo no cobra una cifra
que ya no se debe; si lo paga de todos modos, llega «por revisar».
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger("despacho.caja")


@receiver(post_save, sender="facturacion.Factura", dispatch_uid="caja_sincronizar_links_factura")
def _factura_guardada(sender, instance, created, **kwargs):
    if created:
        return
    try:
        from .services import sincronizar_links_de_factura
        sincronizar_links_de_factura(instance)
    except Exception:  # noqa: BLE001 — La Caja nunca tumba el guardado de una factura
        logger.exception("caja: no pude sincronizar los links de la factura %s", instance.pk)
