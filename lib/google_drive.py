"""Wrapper de Google Drive — andamiaje S2b.1.5.

**NO está activo en producción todavía.** Las credenciales viven en
La Bóveda en los slots:
    - `google_drive_service_account_json` (JSON de la service account)
    - `google_drive_carpeta_raiz_id` (ID de la carpeta raíz en Drive)

Cuando ambos slots tengan valor válido y los métodos se cableen al
SDK real (sprint S2b.1b), este wrapper se vuelve operativo. Hasta
entonces:

- `drive.service` lanza `NoConfiguradoError` si el JSON no está pegado.
- `drive.subir_archivo()` / `crear_carpeta()` / `obtener_o_crear_carpeta()`
  lanzan `NotImplementedError` con mensaje claro.

Setup completo: ver `docs/SETUP_GOOGLE_DRIVE.md`.
"""

from __future__ import annotations

import json
from typing import Any

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class NoConfiguradoError(Exception):
    """Drive no está configurado en La Bóveda."""


class GoogleDriveWrapper:
    """Singleton perezoso — instancia el cliente API solo cuando se usa."""

    def __init__(self) -> None:
        self._service: Any = None
        self._carpeta_raiz_id: str | None = None

    def _credencial(self, clave: str) -> str | None:
        from ajustes.models.credencial import Credencial
        return Credencial.obtener(clave)

    @property
    def carpeta_raiz_id(self) -> str:
        if self._carpeta_raiz_id is None:
            valor = self._credencial("google_drive_carpeta_raiz_id")
            if not valor:
                raise NoConfiguradoError(
                    "Falta `google_drive_carpeta_raiz_id` en Los Ajustes. "
                    "Ver docs/SETUP_GOOGLE_DRIVE.md paso 5."
                )
            self._carpeta_raiz_id = valor
        return self._carpeta_raiz_id

    @property
    def service(self) -> Any:
        if self._service is None:
            json_str = self._credencial("google_drive_service_account_json")
            if not json_str:
                raise NoConfiguradoError(
                    "Falta `google_drive_service_account_json` en Los Ajustes. "
                    "Ver docs/SETUP_GOOGLE_DRIVE.md."
                )
            try:
                creds_info = json.loads(json_str)
            except json.JSONDecodeError as exc:
                raise NoConfiguradoError(
                    f"`google_drive_service_account_json` no es JSON válido: {exc}"
                ) from exc

            # Imports deferidos: el paquete `google-api-python-client` es pesado
            # (~50 MB con sus deps); solo se importa cuando el wrapper se usa
            # de verdad. Si llegamos aquí sin las libs, falla con mensaje claro.
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
            except ImportError as exc:
                raise NoConfiguradoError(
                    "Faltan dependencias de Google: instala "
                    "`google-api-python-client` y `google-auth`."
                ) from exc

            credentials = service_account.Credentials.from_service_account_info(
                creds_info, scopes=SCOPES
            )
            self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return self._service

    def esta_configurado(self) -> bool:
        """True si ambos slots tienen valor (no valida JSON ni conectividad)."""
        return bool(
            self._credencial("google_drive_service_account_json")
            and self._credencial("google_drive_carpeta_raiz_id")
        )

    # ── API funcional — pendiente de cableado en S2b.1b ─────────────────────

    def subir_archivo(
        self,
        ruta_local: str,
        nombre_destino: str,
        carpeta_id: str,
        mime_type: str,
    ) -> dict[str, str]:
        """Sube archivo. Activación en S2b.1b — ver docs/SETUP_GOOGLE_DRIVE.md."""
        raise NotImplementedError(
            "Subida a Drive llega en S2b.1b. Configura credenciales primero "
            "(docs/SETUP_GOOGLE_DRIVE.md) y luego el wrapper se cablea."
        )

    def crear_carpeta(self, nombre: str, padre_id: str) -> dict[str, str]:
        """Crea carpeta. Activación en S2b.1b."""
        raise NotImplementedError(
            "Creación de carpeta llega en S2b.1b. Ver docs/SETUP_GOOGLE_DRIVE.md."
        )

    def obtener_o_crear_carpeta(self, nombre: str, padre_id: str) -> dict[str, str]:
        """Idempotente — busca por nombre, crea si no existe. Activación en S2b.1b."""
        raise NotImplementedError(
            "Idempotencia de carpetas llega en S2b.1b. Ver docs/SETUP_GOOGLE_DRIVE.md."
        )


drive = GoogleDriveWrapper()

__all__ = ["GoogleDriveWrapper", "NoConfiguradoError", "drive", "SCOPES"]
