"""Leer un CFDI: de quién es, de cuánto y con qué folio fiscal.

Existe para que las facturas que mandan los proveedores por correo se archiven
solas. Hoy alguien tiene que bajarlas del PAC y subirlas una por una, y por eso
de 36 facturas sólo 1 tiene su CFDI guardado.

**Este XML viene de fuera.** Llega a un buzón al que cualquiera puede
escribir, así que se trata como lo que es: texto hostil hasta que se demuestre
lo contrario.

Dos defensas, y la primera es la que importa:

1. **Se rechaza cualquier XML con `<!DOCTYPE` o `<!ENTITY`.** El parser de la
   biblioteca estándar SÍ expande entidades personalizadas (comprobado), así
   que un archivo de un kilobyte puede inflarse a gigabytes y tumbar el
   proceso — la «bomba de expansión». Un CFDI legítimo del SAT nunca lleva
   DTD ni entidades, así que rechazarlas no pierde nada y cierra el agujero
   sin traer una dependencia nueva.
2. **Tope de tamaño.** Un CFDI pesa unos pocos kilobytes; medio mega ya es
   señal de que eso no es una factura.

Nada aquí lanza: devuelve `LecturaCFDI` con `ok=False` y el motivo.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

#: Un CFDI son unos pocos KB. Medio mega ya no es una factura.
MAX_BYTES = 512 * 1024

#: Espacios de nombres del comprobante. El 4.0 es el vigente; el 3.3 se
#: conserva porque siguen llegando archivos viejos en los correos.
NS_COMPROBANTE = ("http://www.sat.gob.mx/cfd/4", "http://www.sat.gob.mx/cfd/3")
NS_TIMBRE = "http://www.sat.gob.mx/TimbreFiscalDigital"

_PELIGRO = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


@dataclass
class LecturaCFDI:
    ok: bool = False
    error: str = ""
    uuid: str = ""
    total: Decimal | None = None
    subtotal: Decimal | None = None
    moneda: str = ""
    fecha: str = ""
    serie: str = ""
    folio: str = ""
    emisor_rfc: str = ""
    emisor_nombre: str = ""
    receptor_rfc: str = ""
    receptor_nombre: str = ""
    conceptos: list[str] = field(default_factory=list)

    @property
    def referencia(self) -> str:
        """Serie y folio como los escribe el proveedor: «A-1234»."""
        if self.serie and self.folio:
            return f"{self.serie}-{self.folio}"
        return self.folio or self.serie


def _decimal(valor: str | None) -> Decimal | None:
    if not valor:
        return None
    try:
        return Decimal(valor)
    except (InvalidOperation, ValueError, TypeError):
        return None


def leer(contenido: bytes) -> LecturaCFDI:
    """Saca los datos de un CFDI. Nunca lanza."""
    if not contenido:
        return LecturaCFDI(error="El archivo llegó vacío.")
    if len(contenido) > MAX_BYTES:
        return LecturaCFDI(
            error=f"El archivo pesa {len(contenido) // 1024} KB; un CFDI no llega a eso.")
    if _PELIGRO.search(contenido):
        # Es la defensa principal, y su ausencia sería un agujero de verdad.
        return LecturaCFDI(
            error="El archivo trae definiciones de tipo o entidades. Un CFDI no las lleva.")

    import xml.etree.ElementTree as ET

    try:
        raiz = ET.fromstring(contenido)
    except ET.ParseError as exc:
        return LecturaCFDI(error=f"No se pudo leer el XML: {str(exc)[:120]}")

    etiqueta = raiz.tag
    if not any(f"{{{ns}}}" in etiqueta for ns in NS_COMPROBANTE):
        return LecturaCFDI(
            error="El XML no es un comprobante fiscal (CFDI 3.3 o 4.0).")

    lec = LecturaCFDI(ok=True)
    lec.total = _decimal(raiz.get("Total"))
    lec.subtotal = _decimal(raiz.get("SubTotal"))
    lec.moneda = (raiz.get("Moneda") or "").strip()
    lec.fecha = (raiz.get("Fecha") or "").strip()
    lec.serie = (raiz.get("Serie") or "").strip()
    lec.folio = (raiz.get("Folio") or "").strip()

    for hijo in raiz.iter():
        corto = hijo.tag.rsplit("}", 1)[-1]
        if corto == "Emisor":
            lec.emisor_rfc = (hijo.get("Rfc") or hijo.get("rfc") or "").strip().upper()
            lec.emisor_nombre = (hijo.get("Nombre") or hijo.get("nombre") or "").strip()
        elif corto == "Receptor":
            lec.receptor_rfc = (hijo.get("Rfc") or hijo.get("rfc") or "").strip().upper()
            lec.receptor_nombre = (hijo.get("Nombre") or hijo.get("nombre") or "").strip()
        elif corto == "TimbreFiscalDigital":
            lec.uuid = (hijo.get("UUID") or hijo.get("uuid") or "").strip().upper()
        elif corto == "Concepto":
            desc = (hijo.get("Descripcion") or "").strip()
            if desc and len(lec.conceptos) < 20:
                lec.conceptos.append(desc[:200])

    if not lec.uuid:
        # Sin folio fiscal no está timbrado: es un borrador o un archivo
        # cualquiera. Se lee igual, pero quien llame debe saberlo.
        lec.error = "El comprobante no trae folio fiscal (UUID): no está timbrado."

    return lec


def es_nuestro(lec: LecturaCFDI, rfc_propio: str) -> bool:
    """¿Nos lo emitieron a nosotros? (somos el receptor)

    Distingue la factura que nos manda un proveedor —un gasto— de la que
    nosotros emitimos a un cliente. Sin esto, un CFDI que le mandamos a alguien
    y que rebota al buzón se archivaría como si fuera una compra.
    """
    if not rfc_propio:
        return False
    return lec.receptor_rfc.upper() == rfc_propio.strip().upper()


__all__ = ["MAX_BYTES", "LecturaCFDI", "es_nuestro", "leer"]
