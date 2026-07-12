"""Validación + subida de adjuntos a Google Drive, reutilizable por módulos.

Centraliza la whitelist de MIME, el límite de tamaño y el **fallback
gracioso**: si Drive no está conectado o la subida falla, `subir()` NUNCA
lanza — devuelve `ResultadoAdjunto(ok=False, error=...)` y el caller decide
si continúa sin adjunto (DOC_03 §: "fallback gracioso si Drive cae").

El Drive vive en la cuenta que dio consentimiento (otra cuenta/dominio que
el del equipo), así que los archivos NO se hacen públicos: se sirven vía
proxy autenticado de El Despacho con `lib.google_drive.drive.descargar()`.
"""

from __future__ import annotations

from dataclasses import dataclass

# 25 MB por archivo (DOC_03).
LIMITE_BYTES = 25 * 1024 * 1024

# Imágenes, PDF y ofimática común. Recibos/comprobantes y adjuntos de recados.
MIME_PERMITIDOS = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    # LC #162: XML del CFDI timbrado (PAC). El navegador lo manda como
    # application/xml o text/xml según el SO.
    "application/xml",
    "text/xml",
}


@dataclass
class ResultadoAdjunto:
    ok: bool
    data: dict | None = None
    error: str = ""


def validar(archivo) -> str:
    """Devuelve "" si el archivo es aceptable, o un mensaje de error en español."""
    nombre = getattr(archivo, "name", "archivo")
    tam = getattr(archivo, "size", None)
    if tam is not None and tam > LIMITE_BYTES:
        return f"«{nombre}» pesa más de 25 MB."
    mime = (getattr(archivo, "content_type", "") or "").lower()
    if mime and mime not in MIME_PERMITIDOS:
        return f"«{nombre}»: tipo de archivo no permitido ({mime})."
    return ""


def subir(archivo, subcarpeta: str | None = None) -> ResultadoAdjunto:
    """Sube `archivo` (UploadedFile de Django) a Drive, dentro de `subcarpeta`
    bajo la carpeta raíz. Fallback gracioso: nunca lanza.

    Devuelve `ResultadoAdjunto`. En éxito, `data` trae la metadata de Drive
    (`id`, `name`, `mimeType`, `size`).
    """
    from lib.google_drive import NoConfiguradoError, drive

    err = validar(archivo)
    if err:
        return ResultadoAdjunto(ok=False, error=err)

    if not drive.esta_configurado():
        return ResultadoAdjunto(
            ok=False,
            error="Google Drive no está conectado (Ajustes → Conectar Google Drive).",
        )

    try:
        carpeta_id = drive.obtener_o_crear_subcarpeta(subcarpeta) if subcarpeta else None
        meta = drive.subir_fileobj(
            archivo,
            nombre_destino=getattr(archivo, "name", "archivo"),
            carpeta_id=carpeta_id,
            mime_type=(getattr(archivo, "content_type", "") or "application/octet-stream"),
        )
    except NoConfiguradoError as exc:
        return ResultadoAdjunto(ok=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — fallback gracioso, no tumbar el flujo
        return ResultadoAdjunto(ok=False, error=f"Drive no respondió: {exc}")

    return ResultadoAdjunto(ok=True, data=meta)
