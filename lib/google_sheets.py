"""Wrapper mínimo de Google Sheets — crea una hoja de cálculo en Drive y la
llena con datos tabulares. Reutiliza la autenticación OAuth del wrapper de
Drive (`lib.google_drive.drive`), así que NO requiere re-consentimiento: el
scope `drive.file` cubre la API de Sheets sobre archivos creados por la app.

Uso típico (export de Tesorería "Crear hoja en Drive"):

    from lib.google_sheets import crear_hoja
    res = crear_hoja(titulo="Tesorería · egresos",
                     encabezados=[...], filas=[[...], ...],
                     subcarpeta="Tesorería")
    # res.ok → res.url es la liga a la hoja en Google.

Fallback gracioso: nunca lanza. Si Drive/Sheets no responde devuelve
`ResultadoHoja(ok=False, error=...)`.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
MIME_SHEET = "application/vnd.google-apps.spreadsheet"
HTTP_TIMEOUT = 30.0


@dataclass
class ResultadoHoja:
    ok: bool
    id: str = ""
    url: str = ""
    error: str = ""


def _crear_archivo_hoja(titulo: str, carpeta_id: str | None) -> str:
    """Crea el archivo de hoja de cálculo (vacío) en Drive vía la API de Drive,
    dentro de `carpeta_id`. Devuelve el spreadsheetId."""
    from lib.google_drive import DRIVE_FILES_URL, drive

    cuerpo: dict = {"name": titulo, "mimeType": MIME_SHEET}
    if carpeta_id:
        cuerpo["parents"] = [carpeta_id]
    with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
        resp = cli.post(
            DRIVE_FILES_URL,
            headers=drive._headers(),
            params={"fields": "id"},
            json=cuerpo,
        )
    resp.raise_for_status()
    return resp.json()["id"]


def _escribir_valores(spreadsheet_id: str, valores: list[list]) -> None:
    """Escribe `valores` (lista de filas) a partir de A1 en la primera pestaña."""
    from lib.google_drive import drive

    with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
        resp = cli.put(
            f"{SHEETS_BASE}/{spreadsheet_id}/values/A1",
            headers=drive._headers(),
            params={"valueInputOption": "RAW"},
            json={"majorDimension": "ROWS", "values": valores},
        )
    resp.raise_for_status()


def crear_hoja(
    *, titulo: str, encabezados: list[str], filas: list[list],
    subcarpeta: str | None = None,
) -> ResultadoHoja:
    """Crea una hoja de cálculo en Drive con `encabezados` + `filas` y devuelve
    su liga. Fallback gracioso (nunca lanza)."""
    from lib.google_drive import NoConfiguradoError, drive

    if not drive.esta_configurado():
        return ResultadoHoja(
            ok=False,
            error="Google Drive no está conectado (Ajustes → Conectar Google Drive).",
        )
    try:
        carpeta_id = drive.obtener_o_crear_subcarpeta(subcarpeta) if subcarpeta else None
        sid = _crear_archivo_hoja(titulo, carpeta_id)
        # Todo a texto/numérico simple — el JSON de Sheets no acepta Decimal/date.
        valores = [list(encabezados)] + [[_celda(c) for c in fila] for fila in filas]
        _escribir_valores(sid, valores)
    except NoConfiguradoError as exc:
        return ResultadoHoja(ok=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — fallback gracioso, no tumbar el flujo
        return ResultadoHoja(ok=False, error=f"Google Sheets no respondió: {exc}")

    return ResultadoHoja(
        ok=True, id=sid, url=f"https://docs.google.com/spreadsheets/d/{sid}",
    )


def _celda(v):
    """Normaliza una celda a un tipo serializable por la API de Sheets."""
    if v is None:
        return ""
    if isinstance(v, str | int | float | bool):
        return v
    return str(v)
