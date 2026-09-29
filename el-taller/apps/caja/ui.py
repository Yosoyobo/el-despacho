"""Los botones de La Caja en las pantallas de otros módulos.

Factura, cotización, ficha del cliente y proyecto piden aquí su botón. Si La
Caja está apagada, si quien mira no tiene `caja.crear_link` o si no hay nada que
cobrar, el botón simplemente no sale (cadena vacía): ningún módulo tiene que
saber cómo decide La Caja.
"""

from __future__ import annotations

import logging

from django.urls import reverse
from django.utils.html import format_html

logger = logging.getLogger("despacho.caja")

CLASE_ACCION = "btn-secundario"


def puede_crear(user) -> bool:
    from lib.permisos import puede_crear_link_caja
    return puede_crear_link_caja(user)


def boton_accion(user, objeto, *, clase: str = CLASE_ACCION) -> str:
    """El botón «💳 Link de pago» para la barra de acciones de una factura o una
    cotización. Abre el modal de La Caja."""
    try:
        from apps.cotizaciones.models import Cotizacion
        from apps.facturacion.models import Factura

        from . import services

        if not puede_crear(user) or not services.configurada():
            return ""
        if services.que_cobrar(objeto) is None:
            return ""
        if isinstance(objeto, Factura):
            url = reverse("caja:link-factura", args=[objeto.pk])
        elif isinstance(objeto, Cotizacion):
            url = reverse("caja:link-cotizacion", args=[objeto.pk])
        else:
            return ""
        return format_html(
            '<button type="button" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML" '
            'class="{}" title="Genera (o reusa) el link para que el cliente pague en línea.">'
            "💳 Link de pago</button>",
            url, clase,
        )
    except Exception:  # noqa: BLE001 — un botón nunca tumba la pantalla que lo pide
        logger.exception("caja: no pude armar el botón de link de pago")
        return ""


def boton_libre(user, *, cliente=None, proyecto=None, clase: str = CLASE_ACCION,
                texto: str = "💳 Cobrar con link") -> str:
    """El botón de monto libre para la ficha del cliente o del proyecto."""
    try:
        from . import services

        if not puede_crear(user) or not services.configurada():
            return ""
        base = reverse("caja:link-libre")
        if proyecto is not None:
            url = f"{base}?proyecto={proyecto.pk}"
        elif cliente is not None:
            url = f"{base}?cliente={cliente.pk}"
        else:
            return ""
        return format_html(
            '<button type="button" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML" '
            'class="{}" title="Un link para que el cliente pague un monto que tú escribes.">{}</button>',
            url, clase, texto,
        )
    except Exception:  # noqa: BLE001
        logger.exception("caja: no pude armar el botón de monto libre")
        return ""
