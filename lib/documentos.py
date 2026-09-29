"""Generación de documentos PDF, reutilizable por módulos.

**Quién arma el PDF (cambió el 2026-08-24).** Primero se le pide a
**Gotenberg**, que corre en el NUC y convierte con Chromium; si no responde,
se cae al camino de siempre por Google Docs. La regla §8 seguía prohibiendo
una librería local —WeasyPrint, ReportLab, Puppeteer embebido— y eso no
cambia: Gotenberg es un servicio aparte al que se le habla por HTTP, igual que
a Google, sólo que sin OAuth que caduque ni cuota que agotar.

El cambio arregla deuda concreta: el pie que decía «1/1» en documentos de
varias hojas, el margen superior que Google ignoraba, y los bloques que se
partían pese al CSS. Ver `lib.gotenberg`.

**Dónde se guarda no cambió**: el PDF sigue subiéndose a Drive y sirviéndose
por el proxy autenticado de cada app. Lo único que se reemplazó es quién lo
convierte, para que el resto —`pdf_file_id`, descargas, enlaces— siga igual.

Aquí se centraliza el **fallback gracioso**: si nada puede generar el PDF,
`generar_pdf()` NUNCA lanza — devuelve `ResultadoPdf(ok=False, error=...)` y
el caller decide (p.ej. mostrar un mensaje y no romper «enviar cotización»).

El PDF queda guardado como archivo real en Drive (en `subcarpeta` bajo la
carpeta raíz) y se sirve vía el proxy autenticado de cada app — el Drive vive
en otra cuenta, así que los archivos no se hacen públicos.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

#: Caché del ajuste. Se relee cada minuto: leerlo de la base en cada PDF sería
#: un viaje de más, y guardarlo para siempre obligaría a reiniciar para que un
#: cambio del GUI surtiera efecto.
_TTL_CONFIG = 60.0
_config_cacheada: tuple[float, object] | None = None


def _config():
    """`ConfiguracionDocumento`, o None si aún no hay tabla o base.

    Devuelve None sin ruido cuando la migración no ha corrido: quien llama cae
    a los valores de siempre. Un ajuste que no se puede leer no debe impedir
    que salga un documento.
    """
    global _config_cacheada
    import time

    ahora = time.monotonic()
    if _config_cacheada is not None and ahora - _config_cacheada[0] < _TTL_CONFIG:
        return _config_cacheada[1]
    try:
        from ajustes.models import ConfiguracionDocumento

        cfg = ConfiguracionDocumento.obtener()
    except Exception as exc:  # noqa: BLE001 — sin ajuste se usa el default
        logger.debug("sin ConfiguracionDocumento (%s); se usan los valores por defecto", exc)
        cfg = None
    _config_cacheada = (ahora, cfg)
    return cfg


def olvidar_configuracion() -> None:
    """Tira el caché. La llama el GUI al guardar, para que el cambio se vea ya."""
    global _config_cacheada
    _config_cacheada = None


def pagina_configurada(default: dict | None = None) -> dict:
    """Los márgenes y el pie que eligió el usuario en La Gerencia.

    `default` es lo que se usa si nadie ha configurado nada — los valores con
    los que el documento se ha estado imprimiendo hasta hoy.
    """
    cfg = _config()
    if cfg is None:
        return dict(default or {})
    return cfg.como_pagina()


def marca_borrador() -> str:
    """El texto que se estampa en los documentos sin enviar. Vacío = ninguno."""
    cfg = _config()
    return (getattr(cfg, "marca_borrador", "") or "").strip()


def motor_preferido() -> str:
    """`auto`, `gotenberg` o `google`, según el GUI. `auto` si no hay ajuste."""
    cfg = _config()
    return getattr(cfg, "motor", "auto") or "auto"


@dataclass
class ResultadoPdf:
    ok: bool
    data: dict | None = None   # metadata de Drive: id, name, webViewLink
    pdf_bytes: bytes | None = None
    error: str = ""
    #: Quién lo armó: "gotenberg" o "google". Sirve para diagnosticar por qué
    #: un documento salió con un formato y no con otro.
    motor: str = ""
    #: Lo que salió bien pero no del todo — p. ej. un anexo que no se pudo pegar.
    #: El documento existe; esto es lo que quien lo pidió tiene que saber.
    avisos: list[str] = field(default_factory=list)


def _con_anexos(pdf_bytes: bytes, anexos: list[bytes] | None) -> tuple[bytes, list[str]]:
    """Pega `anexos` al final del PDF. Nunca lanza.

    Si no se pueden unir (Gotenberg caído, un anexo corrupto), el documento sale
    SIN ellos y se avisa: una cotización sin su ficha técnica es mejor que una
    cotización que no sale.
    """
    utiles = [a for a in (anexos or []) if a]
    if not utiles or not pdf_bytes:
        return pdf_bytes, []
    from lib import gotenberg

    try:
        if not gotenberg.disponible():
            raise RuntimeError("el servicio que une los PDF no está contestando")
        return gotenberg.unir([pdf_bytes, *utiles]), []
    except Exception as exc:  # noqa: BLE001 — el documento sale sin anexos
        logger.warning("documentos: no se pudieron pegar los anexos: %s", exc)
        return pdf_bytes, [f"El PDF salió sin sus anexos: {exc}."]


def generar_pdf(
    *, html: str, nombre: str, subcarpeta: str | None = None,
    pagina: dict | None = None, anexos: list[bytes] | None = None,
    html_google=None,
) -> ResultadoPdf:
    """Genera un PDF desde `html` y lo guarda en Drive. Fallback gracioso.

    `nombre` es el nombre del archivo (sin requerir `.pdf`). `subcarpeta`
    organiza el archivo bajo la carpeta raíz (p.ej. "Cotizaciones").
    `pagina` (opcional) ajusta márgenes y pie del documento — ver
    `lib.google_drive.GoogleDriveWrapper._ajustar_pagina`. Quien no lo manda
    conserva los márgenes por default de Google.

    `anexos` (opcional, Sep28): PDFs que se pegan AL FINAL, en ese orden — las
    fichas técnicas de la cotización. Se pegan ANTES de guardar en Drive, así la
    copia guardada es la misma que se descarga y se manda por correo.

    `html_google` (opcional, La Imprenta): el HTML que se le da a Google si es
    Google quien acaba armando el documento — el de «formato de siempre», sin
    los ajustes visuales que Google no respeta. Puede ser el texto o una función
    que lo devuelve, para no dibujarlo dos veces cuando Chromium contesta.
    """
    from lib import gotenberg
    from lib.google_drive import NoConfiguradoError, drive

    # ── Camino nuevo: Chromium aquí mismo ───────────────────────────────────
    # Se intenta primero porque es el que respeta el CSS y numera las páginas.
    # Se cae al de Google si el servicio no contesta — o si alguien lo eligió
    # así desde La Gerencia, que es la salida de emergencia para volver al
    # formato anterior sin esperar un despliegue.
    motor = motor_preferido()
    if motor != "google" and gotenberg.disponible():
        try:
            pdf_bytes = gotenberg.html_a_pdf(html, pagina=pagina)
        except Exception as exc:  # noqa: BLE001 — se intenta con Google
            logger.warning("gotenberg falló, se intenta con Google: %s", exc)
        else:
            pdf_bytes, avisos = _con_anexos(pdf_bytes, anexos)
            nombre_pdf = nombre if nombre.lower().endswith(".pdf") else f"{nombre}.pdf"
            if not drive.esta_configurado():
                # El documento existe aunque no haya dónde guardarlo. Se
                # devuelve para que el caller pueda al menos entregarlo.
                return ResultadoPdf(
                    ok=False, pdf_bytes=pdf_bytes, motor="gotenberg", avisos=avisos,
                    error="El PDF se generó pero Google Drive no está conectado para guardarlo.",
                )
            try:
                carpeta_id = drive.obtener_o_crear_subcarpeta(subcarpeta) if subcarpeta else None
                meta = drive._subir_contenido(
                    pdf_bytes, nombre_pdf, carpeta_id, "application/pdf")
            except Exception as exc:  # noqa: BLE001
                return ResultadoPdf(
                    ok=False, pdf_bytes=pdf_bytes, motor="gotenberg", avisos=avisos,
                    error=f"El PDF se generó pero no se pudo guardar en Drive: {exc}",
                )
            return ResultadoPdf(ok=True, data=meta, pdf_bytes=pdf_bytes,
                                motor="gotenberg", avisos=avisos)

    # ── Camino de siempre: la conversión de Google ──────────────────────────
    if not drive.esta_configurado():
        return ResultadoPdf(
            ok=False,
            error="Google Drive no está conectado (Ajustes → Conectar Google Drive).",
        )
    if html_google is not None:
        try:
            html = html_google() if callable(html_google) else html_google
        except Exception as exc:  # noqa: BLE001 — se usa el mismo HTML
            logger.warning("documentos: no se pudo armar la versión para Google: %s", exc)
        # Las fuentes pegadas no le sirven a Google (baja el HTML solo).
        pagina = {k: v for k, v in (pagina or {}).items() if k != "fuentes"}
    try:
        carpeta_id = drive.obtener_o_crear_subcarpeta(subcarpeta) if subcarpeta else None
        meta = drive.html_a_pdf(
            html=html, nombre=nombre, carpeta_id=carpeta_id, pagina=pagina)
    except NoConfiguradoError as exc:
        return ResultadoPdf(ok=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — fallback gracioso, no tumbar el flujo
        return ResultadoPdf(ok=False, error=f"Drive no pudo generar el PDF: {exc}")

    pdf_bytes = meta.pop("pdf_bytes", None)
    avisos: list[str] = []
    if anexos and pdf_bytes:
        # Google ya guardó el PDF SIN anexos. Si se pueden pegar, se guarda la
        # versión completa y se borra la otra, para que lo guardado siga siendo
        # lo mismo que se descarga.
        completo, avisos = _con_anexos(pdf_bytes, anexos)
        if completo is not pdf_bytes:
            try:
                carpeta_id = drive.obtener_o_crear_subcarpeta(subcarpeta) if subcarpeta else None
                nombre_pdf = nombre if nombre.lower().endswith(".pdf") else f"{nombre}.pdf"
                nueva = drive._subir_contenido(completo, nombre_pdf, carpeta_id,
                                               "application/pdf")
                with contextlib.suppress(Exception):
                    drive.borrar(meta.get("id", ""))
                meta = nueva
            except Exception as exc:  # noqa: BLE001 — se entrega igual, completo
                logger.warning("documentos: no se pudo guardar la versión con "
                               "anexos en Drive: %s", exc)
            pdf_bytes = completo
    return ResultadoPdf(ok=True, data=meta, pdf_bytes=pdf_bytes, motor="google",
                        avisos=avisos)
