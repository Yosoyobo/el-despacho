"""Correos automáticos de El Cartero (S-LC-Feedback-V6 Bloque 7A).

Bienvenida al alta de cliente + confirmación de pago al registrar un ingreso.
Gobernados por los flags `auto_bienvenida` / `auto_pago` de
`ajustes.ConfiguracionCorreo` (ARRANCAN APAGADOS). Best-effort total: un
correo fallido jamás tumba el alta del cliente ni el registro del ingreso.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _config():
    from ajustes.models.cartero import ConfiguracionCorreo
    return ConfiguracionCorreo.obtener()


def _render_y_enviar(slug: str, destinatario: str, contexto: dict) -> bool:
    from ajustes.models.plantilla_correo import PlantillaCorreo
    from lib import cartero

    plantilla = PlantillaCorreo.obtener(slug)
    asunto, html = plantilla.render(contexto)
    resultado = cartero.enviar(destinatario=destinatario, asunto=asunto, html=html)
    return bool(getattr(resultado, "ok", False))


def enviar_bienvenida(cliente) -> bool:
    """Bienvenida al crear un Cliente con email. Best-effort; respeta el flag."""
    try:
        if not _config().auto_bienvenida:
            return False
        email = (cliente.email_contacto or "").strip()
        if not email:
            return False
        from django.utils import timezone
        ok = _render_y_enviar("bienvenida", email, {
            "cliente": cliente.nombre_contacto or cliente.razon_social,
            "representante": "",
            "fecha": timezone.localdate().strftime("%d/%m/%Y"),
        })
        if ok:
            _emitir("correo.bienvenida_enviado", {"cliente_id": cliente.pk})
        return ok
    except Exception:  # noqa: BLE001 — nunca tumbar el alta
        logger.warning("Correo de bienvenida falló (cliente=%s)", getattr(cliente, "pk", None), exc_info=True)
        return False


def enviar_confirmacion_pago(ingreso) -> bool:
    """Confirmación de pago al registrar un Ingreso vigente con cliente+email."""
    try:
        if not _config().auto_pago:
            return False
        cliente = getattr(ingreso, "cliente", None)
        if cliente is None or getattr(ingreso, "anulado", False):
            return False
        email = (cliente.email_contacto or "").strip()
        if not email:
            return False
        ok = _render_y_enviar("pago", email, {
            "cliente": cliente.nombre_contacto or cliente.razon_social,
            "monto": f"{ingreso.monto:,.2f}",
            "moneda": "MXN",
            "referencia": getattr(ingreso, "codigo", "") or "",
            "metodo": ingreso.get_metodo_display() if hasattr(ingreso, "get_metodo_display") else "",
            "fecha": ingreso.fecha.strftime("%d/%m/%Y") if getattr(ingreso, "fecha", None) else "",
        })
        if ok:
            _emitir("correo.pago_enviado", {"ingreso_id": ingreso.pk, "cliente_id": cliente.pk})
        return ok
    except Exception:  # noqa: BLE001 — nunca tumbar el registro del ingreso
        logger.warning("Correo de pago falló (ingreso=%s)", getattr(ingreso, "pk", None), exc_info=True)
        return False


def _emitir(tipo: str, payload: dict) -> None:
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(tipo=tipo, actor_id=None, actor_email="sistema", payload=payload))
    except Exception:  # noqa: BLE001
        pass
