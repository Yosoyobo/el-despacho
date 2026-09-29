"""El código QR de los documentos (La Imprenta).

Se dibuja con `segno` como SVG y va DENTRO del HTML como `data:` — Chromium lo
pinta nítido a cualquier tamaño y no hay archivo que alojar. Google no entiende
imágenes `data:`, por eso el QR es un ajuste «visual» y en el camino de Google no
sale (decisión de Oscar: Google saca el documento con el formato de siempre).

**Nunca se mete una llave de acceso en el QR**: el del portal apunta a la
entrada de La Recepción, donde el cliente pide su enlace con su correo. Un PDF
se reenvía y se imprime; una llave dentro sería de quien lo tenga en la mano.
"""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


def data_uri(url: str) -> str:
    """`data:image/svg+xml;base64,…` del QR de `url`. "" si no se puede."""
    if not url:
        return ""
    try:
        import io

        import segno

        buf = io.BytesIO()
        segno.make(url, error="m").save(buf, kind="svg", scale=4, border=1,
                                        dark="#000000", light=None, xmldecl=False)
        return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:  # noqa: BLE001 — sin QR, el documento sale igual
        logger.warning("imprenta: no se pudo dibujar el QR: %s", exc)
        return ""


def url_portal() -> str:
    """La entrada del portal de clientes. "" si no está en esta instalación."""
    try:
        from portal.servicios import url_recepcion

        return url_recepcion()
    except Exception:  # noqa: BLE001
        return ""


def url_pago(objeto) -> str:
    """El link de pago de La Caja para una factura o cotización. "" si no hay."""
    try:
        from apps.caja.services import url_pago as _url

        return _url(objeto) or ""
    except Exception:  # noqa: BLE001 — La Caja no instalada o apagada
        return ""


__all__ = ["data_uri", "url_pago", "url_portal"]
