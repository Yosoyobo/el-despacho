"""Avisos del Interfón de La Caja.

A quién: a quien ve La Caja (`caja.ver`), nunca a un rol (§4 #20). Es el mismo
permiso de la casilla «La Caja · pagos en línea» de /perfil/notificaciones/,
así que nadie ve un interruptor de algo que nunca le llega.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("despacho.caja")

PERMISO_CAJA = ("caja", "ver")
CATEGORIA = "caja"


def _destinatarios():
    from lib.permisos import usuarios_con_permiso
    return usuarios_con_permiso(*PERMISO_CAJA)


def notificar_pago(pago) -> None:
    """Pago registrado o por revisar. Fuera de la petición del webhook: la
    pasarela no tiene por qué esperar a que Apple y Google acusen recibo."""
    from lib.tareas_fondo import ejecutar_en_fondo

    ejecutar_en_fondo(_notificar, pago.pk)


def _notificar(pago_id: int) -> None:
    from lib.interfono import enviar_a_usuario

    from .models import PagoRecibido
    from .services import _dinero

    pago = PagoRecibido.objects.select_related("link", "link__cliente").filter(pk=pago_id).first()
    if pago is None:
        return
    link = pago.link
    quien = getattr(getattr(link, "cliente", None), "razon_social", "") or "Un cliente"
    que = link.referencia if link else "un link de pago"
    if pago.estado == "registrado":
        titulo = f"💳 Pago recibido: {_dinero(pago.monto)}"
        cuerpo = f"{quien} pagó {que} en línea. Ya quedó registrado."
    else:
        titulo = f"⚠️ Pago por revisar: {_dinero(pago.monto)}"
        cuerpo = f"{quien} pagó {que}, pero no cuadró: {pago.motivo}"[:240]
    for usuario in _destinatarios():
        try:
            enviar_a_usuario(
                usuario, titulo=titulo, cuerpo=cuerpo, url="/tesoreria/caja/",
                tag=f"caja-pago-{pago.pk}", categoria=CATEGORIA,
                origen_modulo="caja", origen_id=pago.pk,
            )
        except Exception:  # noqa: BLE001 — un push roto no tumba nada
            logger.exception("push de La Caja falló (usuario=%s)", usuario.pk)
