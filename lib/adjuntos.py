"""Validación + subida de adjuntos, reutilizable por módulos.

Centraliza la whitelist de MIME, el límite de tamaño y el **fallback
gracioso**: si algo falla, `subir()` NUNCA lanza — devuelve
`ResultadoAdjunto(ok=False, error=...)` y el caller decide si continúa sin
adjunto (DOC_03 §: "fallback gracioso si Drive cae").

**S-Medios-V1 (LC 2026-08-20): el archivo se guarda en disco, en El Almacén**
(`lib/almacen.py`), que es la fuente de verdad para leerlo. Drive queda como
**espejo**: recibe una copia en la subida, así se conserva la durabilidad fuera
del servidor y la carpeta navegable a mano, pero deja de estar en el camino de
lectura. Antes cada foto que alguien miraba eran dos llamadas a la API de Google.

Consecuencia a favor: **si Drive falla, la subida ya no falla.** Antes, sin Drive
conectado no se podía adjuntar nada; ahora el archivo queda guardado y el espejo
simplemente no se hace.

Los archivos siguen sin ser públicos en Drive: se sirven desde El Almacén, los
documentos por su vista autenticada y las imágenes por El Portero con una ruta
que lleva la huella de su contenido.
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


def subir(archivo, subcarpeta: str | None = None, *, espejo: bool = True) -> ResultadoAdjunto:
    """Guarda `archivo` (UploadedFile de Django) en El Almacén y lo espeja a
    Drive dentro de `subcarpeta`. Fallback gracioso: nunca lanza.

    Devuelve `ResultadoAdjunto`. En éxito, `data` conserva la misma forma que
    antes traía la metadata de Drive (`id`, `name`, `mimeType`, `size`,
    `webViewLink`), así que los ~10 puntos de subida del repo no cambian. Lo que
    cambia es qué es el `id`: la llave de El Almacén (el sha256 del contenido) en
    lugar del id de Drive. Como todas las columnas que lo guardan son cadenas
    opacas de 100 caracteres o más, **no hace falta ninguna migración**.

    `espejo=False` guarda sólo en disco (lo usa la importación, que ya viene de
    Drive y no tiene nada que espejar).
    """
    err = validar(archivo)
    if err:
        return ResultadoAdjunto(ok=False, error=err)

    nombre = getattr(archivo, "name", "archivo") or "archivo"
    mime = (getattr(archivo, "content_type", "") or "application/octet-stream")

    # 1) El Almacén — la copia que se va a leer.
    guardado: dict | None = None
    try:
        from lib import almacen

        guardado = almacen.guardar_fileobj(archivo, mime=mime, nombre=nombre)
    except Exception as exc:  # noqa: BLE001 — disco lleno, permisos, ruta mal montada
        error_disco = f"El Almacén no pudo guardar el archivo: {exc}"
    else:
        error_disco = ""

    # 2) Drive — el espejo. Se sube desde el archivo YA guardado, no del
    #    `UploadedFile`, para no depender de poder releerlo.
    meta_drive: dict | None = None
    error_drive = ""
    if espejo:
        ruta_local = ""
        if guardado:
            from lib import almacen

            ruta = almacen._dir_orig(guardado["id"]) / "archivo"
            ruta_local = str(ruta) if ruta.is_file() else ""
        meta_drive, error_drive = _espejar_en_drive(
            archivo, subcarpeta, nombre=nombre, mime=mime, ruta_local=ruta_local,
        )

    if guardado is None:
        # El disco falló. Si el espejo respondió, se usa su id y El Almacén lo
        # importará solo la primera vez que alguien lo lea.
        if meta_drive:
            return ResultadoAdjunto(ok=True, data=meta_drive)
        return ResultadoAdjunto(ok=False, error=error_disco or error_drive)

    if meta_drive:
        _anotar_espejo(guardado["id"], meta_drive.get("id", ""))

    return ResultadoAdjunto(ok=True, data={
        "id": guardado["id"],
        "name": guardado.get("nombre", nombre),
        "mimeType": guardado.get("mime", mime),
        "size": str(guardado.get("bytes", "")),
        # Enlace a la copia de Drive si el espejo se hizo; vacío si no. Los
        # llamadores lo guardan como referencia — la miniatura NUNCA sale de ahí.
        "webViewLink": (meta_drive or {}).get("webViewLink", ""),
        "espejo_drive": (meta_drive or {}).get("id", ""),
        "error_espejo": error_drive,
    })


def _espejar_en_drive(archivo, subcarpeta, *, nombre: str, mime: str,
                      ruta_local: str) -> tuple[dict | None, str]:
    """Sube la copia a Drive. Best-effort: devuelve `(None, motivo)` si no se pudo."""
    from lib.google_drive import NoConfiguradoError, drive

    if not drive.esta_configurado():
        return None, "Google Drive no está conectado (Ajustes → Conectar Google Drive)."
    try:
        carpeta_id = drive.obtener_o_crear_subcarpeta(subcarpeta) if subcarpeta else None
        if ruta_local:
            meta = drive.subir_archivo(ruta_local, nombre_destino=nombre,
                                       carpeta_id=carpeta_id, mime_type=mime)
        else:
            meta = drive.subir_fileobj(archivo, nombre_destino=nombre,
                                       carpeta_id=carpeta_id, mime_type=mime)
    except NoConfiguradoError as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001 — Drive caído: el archivo ya está en disco
        return None, f"Drive no respondió: {exc}"
    return meta, ""


def _anotar_espejo(clave: str, drive_file_id: str) -> None:
    """Deja constancia en el `meta.json` de dónde quedó la copia de Drive."""
    if not drive_file_id:
        return
    try:
        from lib import almacen

        datos = almacen.meta(clave) or {}
        almacen._escribir_meta(clave, {**datos, "drive_file_id": drive_file_id})
    except Exception:  # noqa: BLE001 — es una anotación, no puede tumbar la subida
        pass
