"""Generación de documentos PDF vía Google Drive, reutilizable por módulos.

Regla §8: el PDF lo produce Google (HTML → Google Doc → export PDF), NO una
librería local (WeasyPrint/ReportLab/Puppeteer). La orquestación vive en
`lib.google_drive.drive.html_a_pdf`; aquí centralizamos el **fallback
gracioso**: si Drive no está conectado o la generación falla, `generar_pdf()`
NUNCA lanza — devuelve `ResultadoPdf(ok=False, error=...)` y el caller decide
(p.ej. mostrar un mensaje y no romper el flujo de "enviar cotización").

El PDF queda guardado como archivo real en Drive (en `subcarpeta` bajo la
carpeta raíz) y se sirve vía el proxy autenticado de cada app — el Drive vive
en otra cuenta, así que los archivos no se hacen públicos.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ResultadoPdf:
    ok: bool
    data: dict | None = None   # metadata de Drive: id, name, webViewLink
    pdf_bytes: bytes | None = None
    error: str = ""


def generar_pdf(*, html: str, nombre: str, subcarpeta: str | None = None) -> ResultadoPdf:
    """Genera un PDF desde `html` y lo guarda en Drive. Fallback gracioso.

    `nombre` es el nombre del archivo (sin requerir `.pdf`). `subcarpeta`
    organiza el archivo bajo la carpeta raíz (p.ej. "Cotizaciones").
    """
    from lib.google_drive import NoConfiguradoError, drive

    if not drive.esta_configurado():
        return ResultadoPdf(
            ok=False,
            error="Google Drive no está conectado (Ajustes → Conectar Google Drive).",
        )
    try:
        carpeta_id = drive.obtener_o_crear_subcarpeta(subcarpeta) if subcarpeta else None
        meta = drive.html_a_pdf(html=html, nombre=nombre, carpeta_id=carpeta_id)
    except NoConfiguradoError as exc:
        return ResultadoPdf(ok=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — fallback gracioso, no tumbar el flujo
        return ResultadoPdf(ok=False, error=f"Drive no pudo generar el PDF: {exc}")

    pdf_bytes = meta.pop("pdf_bytes", None)
    return ResultadoPdf(ok=True, data=meta, pdf_bytes=pdf_bytes)
