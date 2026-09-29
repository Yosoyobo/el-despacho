"""Word y Excel se vuelven PDF antes de guardarse — una sola regla, tres puertas.

La usan las dos puertas del papeleo (la subida desde El Taller y el buzón del
robot) y los anexos de la cotización. Un solo lugar para que conviertan
exactamente igual: si cada uno tuviera su copia, tarde o temprano uno aceptaría
un `.pptx` que el otro rechaza.

**Por qué convertir.** Paperless sin su módulo de Office (Tika) no sabe leer un
`.docx`: lo rechaza o lo guarda sin texto, y un documento sin texto no se
encuentra por lo que dice adentro. Y un anexo sólo se puede pegar al final de la
cotización si es PDF. Gotenberg (LibreOffice, en el NUC) resuelve las dos.

**El nombre se conserva**: «Contrato Optimist.docx» queda como
«Contrato Optimist.pdf», así el documento se sigue reconociendo por como lo nombró
quien lo mandó.

**Si Gotenberg no contesta, se queda el original y se avisa.** Perder el
documento por un convertidor caído sería peor que tenerlo sin convertir. Nunca
lanza: lo peor que devuelve es un `aviso`.

Sin Django: vive en `lib/` y se puede llamar desde un command o un worker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Preparado:
    """Lo que se va a archivar, después de intentar convertirlo."""

    contenido: bytes
    nombre: str
    #: El archivo era de Office y quedó convertido a PDF.
    convertido: bool = False
    #: Era de Office pero NO se pudo convertir: se queda el original.
    aviso: str = ""


def _convertibles() -> tuple[str, ...]:
    """Lo de Office que se convierte. CSV se queda fuera a propósito: es un dato,
    no un documento (Paperless lo lee como texto sin ayuda, y como anexo de una
    cotización no tiene sentido)."""
    from lib import gotenberg

    return tuple(e for e in gotenberg.EXTENSIONES_OFFICE if e != ".csv")


def es_convertible(nombre: str) -> bool:
    return (nombre or "").lower().endswith(_convertibles())


def nombre_pdf(nombre: str) -> str:
    """«Contrato.docx» → «Contrato.pdf». Conserva todo lo de antes del punto."""
    base = (nombre or "documento").rsplit(".", 1)[0] or "documento"
    return f"{base}.pdf"


def preparar(contenido: bytes, nombre: str) -> Preparado:
    """Convierte si hace falta. Nunca lanza: lo peor que pasa es un aviso."""
    nombre = nombre or "documento"
    if not es_convertible(nombre):
        return Preparado(contenido=contenido, nombre=nombre)

    from lib import gotenberg

    try:
        if not gotenberg.disponible():
            raise RuntimeError("el convertidor no está contestando")
        pdf = gotenberg.office_a_pdf(contenido, nombre)
        if not pdf:
            raise RuntimeError("el convertidor devolvió un archivo vacío")
    except Exception as exc:  # noqa: BLE001 — se queda el original
        logger.warning("a_pdf: no se pudo convertir %s: %s", nombre, exc)
        return Preparado(
            contenido=contenido, nombre=nombre,
            aviso=f"«{nombre}» no se pudo pasar a PDF ({exc}); se guardó el original.",
        )
    return Preparado(contenido=pdf, nombre=nombre_pdf(nombre), convertido=True)


__all__ = ["Preparado", "es_convertible", "nombre_pdf", "preparar"]
