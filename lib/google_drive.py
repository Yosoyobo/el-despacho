"""Wrapper de Google Drive — autenticación SIN archivo de clave (Opción B).

La organización de Learning Center bloquea la creación de claves de cuentas
de servicio (`iam.disableServiceAccountKeyCreation`), así que NO usamos un
JSON de service account. En su lugar usamos **OAuth con token de
actualización**:

1. El admin da consentimiento una vez con la cuenta corporativa (asistente
   en `/ajustes/google-drive/`). Reutilizamos el MISMO cliente OAuth del
   login con Google (slots `google_oauth_client_id` / `_secret`).
2. Guardamos el `refresh_token` cifrado en La Bóveda
   (`google_drive_oauth_refresh_token`).
3. Cada vez que se necesita, el wrapper canjea ese refresh token por un
   `access_token` de corta vida y llama a la API REST de Drive con httpx
   (mismo patrón que `lib/google_oauth.py`, sin dependencias pesadas).

Alcance: `drive.file` — el sistema solo ve/toca lo que él mismo crea. Por
eso crea su propia carpeta raíz "El Despacho - Adjuntos" en la Mi unidad de
la cuenta que dio consentimiento, y guarda su ID en
`google_drive_carpeta_raiz_id`.

Setup completo: el asistente en La Gerencia → Ajustes → Conectar Google
Drive. Referencia técnica: `docs/SETUP_GOOGLE_DRIVE.md`.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx

# Scope mínimo: solo archivos creados por la app. NO es scope sensible, así
# que no requiere verificación de Google.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
CARPETA_RAIZ_NOMBRE = "El Despacho - Adjuntos"
HTTP_TIMEOUT = 10.0
# Subir/bajar archivos puede tardar más que un ping; damos margen.
HTTP_TIMEOUT_ARCHIVO = 60.0

MIME_CARPETA = "application/vnd.google-apps.folder"


class NoConfiguradoError(Exception):
    """Drive no está conectado (falta el cliente OAuth o el refresh token)."""


# ── Helpers de credenciales ──────────────────────────────────────────────────


def _credencial(clave: str) -> str | None:
    from ajustes.models.credencial import Credencial
    return Credencial.obtener(clave)


def parsear_cliente_json(texto: str) -> dict[str, Any]:
    """Extrae client_id / client_secret / redirect_uris del JSON descargado de
    Google Cloud (formato {"web": {...}} o {"installed": {...}}).

    Lanza ValueError con mensaje claro si el JSON no tiene la forma esperada.
    """
    import json
    try:
        data = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ValueError(f"El archivo no es un JSON válido: {exc}") from exc

    bloque = data.get("web") or data.get("installed") or data
    cid = bloque.get("client_id")
    sec = bloque.get("client_secret")
    if not cid or not sec:
        raise ValueError(
            "El JSON no trae client_id y client_secret. Asegúrate de pegar el "
            "archivo de 'ID de cliente de OAuth' descargado de Google Cloud."
        )
    return {
        "client_id": cid,
        "client_secret": sec,
        "redirect_uris": bloque.get("redirect_uris", []),
        "project_id": bloque.get("project_id"),
    }


def cliente_id_actual() -> str | None:
    """El client_id en uso (dedicado de Drive o, si no, el del login). No es secreto."""
    return _credencial("google_drive_oauth_client_id") or _credencial("google_oauth_client_id")


def cliente_configurado() -> bool:
    """True si hay un cliente OAuth usable (dedicado de Drive o el del login)."""
    drive_cid = _credencial("google_drive_oauth_client_id")
    drive_sec = _credencial("google_drive_oauth_client_secret")
    if drive_cid and drive_sec:
        return True
    return bool(_credencial("google_oauth_client_id") and _credencial("google_oauth_client_secret"))


def _cliente_oauth() -> tuple[str, str]:
    """(client_id, client_secret) del cliente OAuth.

    Prefiere un cliente DEDICADO de Drive (`google_drive_oauth_client_*`); si
    no está, cae al cliente del login con Google (`google_oauth_client_*`). Esto
    permite usar un cliente aparte para Drive sin tocar el SSO.
    """
    cid = _credencial("google_drive_oauth_client_id") or _credencial("google_oauth_client_id")
    sec = _credencial("google_drive_oauth_client_secret") or _credencial("google_oauth_client_secret")
    if not cid or not sec:
        raise NoConfiguradoError(
            "Falta el cliente OAuth de Google. Pega el archivo de cliente "
            "(JSON) en el asistente, o configura el del login con Google."
        )
    return cid, sec


# ── Flujo de consentimiento (OAuth 3-legged, offline) ─────────────────────────


def construir_url_consentimiento(redirect_uri: str, state: str) -> str:
    """URL para enviar al navegador del admin y pedir consentimiento.

    `access_type=offline` + `prompt=consent` fuerzan que Google devuelva un
    refresh token cada vez (no solo en el primer consentimiento).
    """
    cid, _ = _cliente_oauth()
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def intercambiar_codigo_por_refresh_token(code: str, redirect_uri: str) -> str:
    """Canjea el `code` del callback por un refresh token. Lo retorna crudo."""
    cid, sec = _cliente_oauth()
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
            resp = cli.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": cid,
                    "client_secret": sec,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
    except httpx.HTTPError as exc:
        raise NoConfiguradoError(f"No se pudo contactar a Google: {exc}") from exc

    if resp.status_code >= 400:
        detalle = (resp.json() or {}).get("error", f"http_{resp.status_code}")
        raise NoConfiguradoError(f"Google rechazó el consentimiento: {detalle}")

    data = resp.json()
    refresh = data.get("refresh_token")
    if not refresh:
        raise NoConfiguradoError(
            "Google no devolvió un refresh token. Revoca el acceso anterior de "
            "la app y vuelve a conectar (debe pedir consentimiento de nuevo)."
        )
    return refresh


# ── Wrapper operativo ─────────────────────────────────────────────────────────


class GoogleDriveWrapper:
    """Acceso a Drive vía refresh token. Crea su propia carpeta raíz."""

    def __init__(self) -> None:
        self._carpeta_raiz_id: str | None = None

    def recargar(self) -> None:
        """Olvida la carpeta cacheada (tras reconectar o cambiar credenciales)."""
        self._carpeta_raiz_id = None

    def esta_configurado(self) -> bool:
        """True si hay cliente OAuth + refresh token guardado."""
        return bool(cliente_configurado() and _credencial("google_drive_oauth_refresh_token"))

    def esta_conectado(self) -> bool:
        """True si además la carpeta raíz ya quedó creada y guardada."""
        return self.esta_configurado() and bool(
            _credencial("google_drive_carpeta_raiz_id")
        )

    # ── Auth interno ──────────────────────────────────────────────────────────

    def _access_token(self) -> str:
        """Canjea el refresh token por un access token de corta vida."""
        refresh = _credencial("google_drive_oauth_refresh_token")
        if not refresh:
            raise NoConfiguradoError(
                "Google Drive no está conectado. Usa el asistente: Ajustes → "
                "Conectar Google Drive."
            )
        cid, sec = _cliente_oauth()
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
                resp = cli.post(
                    TOKEN_URL,
                    data={
                        "refresh_token": refresh,
                        "client_id": cid,
                        "client_secret": sec,
                        "grant_type": "refresh_token",
                    },
                )
        except httpx.HTTPError as exc:
            raise NoConfiguradoError(f"No se pudo contactar a Google: {exc}") from exc

        if resp.status_code >= 400:
            detalle = (resp.json() or {}).get("error", f"http_{resp.status_code}")
            raise NoConfiguradoError(
                f"El acceso de Google expiró o fue revocado ({detalle}). "
                "Reconecta desde el asistente."
            )
        return resp.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token()}"}

    # ── Carpetas ────────────────────────────────────────────────────────────

    def crear_carpeta(self, nombre: str, padre_id: str | None = None) -> dict[str, str]:
        """Crea una carpeta en Drive. Sin `padre_id`, queda en la raíz (Mi unidad)."""
        cuerpo: dict[str, Any] = {"name": nombre, "mimeType": MIME_CARPETA}
        if padre_id:
            cuerpo["parents"] = [padre_id]
        with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
            resp = cli.post(
                DRIVE_FILES_URL,
                headers=self._headers(),
                params={"fields": "id,name"},
                json=cuerpo,
            )
        resp.raise_for_status()
        return resp.json()

    def obtener_o_crear_carpeta_raiz(self) -> str:
        """Devuelve el ID de la carpeta raíz; la crea si no existe.

        Idempotente: si el slot ya tiene un ID válido (la carpeta existe),
        lo reusa. Si el ID guardado ya no existe en Drive (la borraron),
        crea una nueva y actualiza el slot.
        """
        if self._carpeta_raiz_id:
            return self._carpeta_raiz_id

        guardado = _credencial("google_drive_carpeta_raiz_id")
        if guardado:
            with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
                resp = cli.get(
                    f"{DRIVE_FILES_URL}/{guardado}",
                    headers=self._headers(),
                    params={"fields": "id,name,trashed"},
                )
            if resp.status_code == 200 and not resp.json().get("trashed"):
                self._carpeta_raiz_id = guardado
                return guardado
            # 404 o en papelera → caemos a crear una nueva.

        creada = self.crear_carpeta(CARPETA_RAIZ_NOMBRE)
        from ajustes.models.credencial import Credencial
        Credencial.guardar("google_drive_carpeta_raiz_id", creada["id"])
        self._carpeta_raiz_id = creada["id"]
        return creada["id"]

    @property
    def carpeta_raiz_id(self) -> str:
        return self.obtener_o_crear_carpeta_raiz()

    # ── Diagnóstico ───────────────────────────────────────────────────────────

    def probar(self) -> dict[str, Any]:
        """Verifica de punta a punta que Drive quedó bien conectado.

        Refresca el access token y asegura la carpeta raíz. Devuelve un dict
        pensado para usuarios no técnicos — `estado` ∈ {no_conectado,
        sin_acceso, error, ok}, `mensaje` en español llano.
        """
        self.recargar()

        if not cliente_configurado():
            return {
                "ok": False,
                "estado": "no_conectado",
                "mensaje": "Falta el cliente OAuth de Google. Pega tu archivo de cliente (JSON) en el paso 2.",
            }
        if not _credencial("google_drive_oauth_refresh_token"):
            return {
                "ok": False,
                "estado": "no_conectado",
                "mensaje": "Aún no has conectado tu cuenta de Google. Usa el botón «Conectar mi cuenta de Google».",
            }

        try:
            carpeta_id = self.obtener_o_crear_carpeta_raiz()
        except NoConfiguradoError as exc:
            return {"ok": False, "estado": "sin_acceso", "mensaje": str(exc)}
        except httpx.HTTPStatusError as exc:
            estatus = exc.response.status_code
            if estatus in (401, 403):
                return {
                    "ok": False,
                    "estado": "sin_acceso",
                    "mensaje": (
                        "Google rechazó el acceso. Asegúrate de haber habilitado "
                        "la API de Drive (paso 1) y vuelve a conectar tu cuenta."
                    ),
                }
            return {"ok": False, "estado": "error", "mensaje": f"Google respondió con error: {exc}"}
        except Exception as exc:  # noqa: BLE001 — atrapar todo para el usuario
            return {"ok": False, "estado": "error", "mensaje": f"No se pudo conectar con Drive: {exc}"}

        return {
            "ok": True,
            "estado": "ok",
            "mensaje": f"¡Listo! Conectado. La carpeta «{CARPETA_RAIZ_NOMBRE}» está lista en tu Drive.",
            "carpeta_id": carpeta_id,
        }

    # ── Subcarpetas ───────────────────────────────────────────────────────────

    def obtener_o_crear_subcarpeta(self, nombre: str, padre_id: str | None = None) -> str:
        """ID de una subcarpeta por nombre bajo `padre_id` (o la raíz); la crea
        si no existe. Sirve para organizar adjuntos (p.ej. «Los Recados»,
        «Comprobantes», «2026-06»). Idempotente.

        Con scope `drive.file` la búsqueda solo ve carpetas que la app creó, que
        es justo lo que queremos.
        """
        padre = padre_id or self.obtener_o_crear_carpeta_raiz()
        nombre_q = nombre.replace("\\", "\\\\").replace("'", "\\'")
        consulta = (
            f"name = '{nombre_q}' and mimeType = '{MIME_CARPETA}' "
            f"and '{padre}' in parents and trashed = false"
        )
        with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
            resp = cli.get(
                DRIVE_FILES_URL,
                headers=self._headers(),
                params={"q": consulta, "fields": "files(id,name)", "pageSize": 1},
            )
        resp.raise_for_status()
        encontrados = resp.json().get("files", [])
        if encontrados:
            return encontrados[0]["id"]
        return self.crear_carpeta(nombre, padre_id=padre)["id"]

    # ── Adjuntos: subir / descargar ───────────────────────────────────────────

    def subir_fileobj(
        self,
        fileobj: Any,
        nombre_destino: str,
        carpeta_id: str | None = None,
        mime_type: str = "application/octet-stream",
    ) -> dict[str, str]:
        """Sube un objeto tipo-archivo (p.ej. `request.FILES['x']`) a Drive.

        Sin `carpeta_id`, lo deja en la carpeta raíz. Devuelve la metadata de
        Drive: `id`, `name`, `mimeType`, `size`, `webViewLink`.
        """
        return self._subir_contenido(fileobj.read(), nombre_destino, carpeta_id, mime_type)

    def subir_archivo(
        self,
        ruta_local: str,
        nombre_destino: str,
        carpeta_id: str | None = None,
        mime_type: str = "application/octet-stream",
    ) -> dict[str, str]:
        """Sube un archivo desde una ruta local del servidor. Misma salida que
        `subir_fileobj`."""
        with open(ruta_local, "rb") as fh:
            contenido = fh.read()
        return self._subir_contenido(contenido, nombre_destino, carpeta_id, mime_type)

    def _subir_contenido(
        self,
        contenido: bytes,
        nombre_destino: str,
        carpeta_id: str | None,
        mime_type: str,
    ) -> dict[str, str]:
        """Subida multipart (metadata + bytes en una sola llamada)."""
        carpeta = carpeta_id or self.obtener_o_crear_carpeta_raiz()
        metadata = {"name": nombre_destino, "parents": [carpeta]}
        frontera = f"despacho_{uuid4().hex}"
        prefijo = (
            f"--{frontera}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{frontera}\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode()
        sufijo = f"\r\n--{frontera}--\r\n".encode()
        cuerpo = prefijo + contenido + sufijo

        headers = self._headers()
        headers["Content-Type"] = f"multipart/related; boundary={frontera}"
        with httpx.Client(timeout=HTTP_TIMEOUT_ARCHIVO) as cli:
            resp = cli.post(
                DRIVE_UPLOAD_URL,
                headers=headers,
                params={
                    "uploadType": "multipart",
                    "fields": "id,name,mimeType,size,webViewLink",
                },
                content=cuerpo,
            )
        resp.raise_for_status()
        return resp.json()

    def descargar(self, file_id: str) -> tuple[bytes, str, str]:
        """Descarga un archivo de Drive. Devuelve `(contenido, mime_type, nombre)`.

        Lo usa el proxy de El Despacho para servir adjuntos a usuarios
        autenticados sin exponer el archivo públicamente en Drive (el Drive
        vive en otra cuenta/dominio que el del equipo).
        """
        headers = self._headers()
        with httpx.Client(timeout=HTTP_TIMEOUT_ARCHIVO) as cli:
            meta = cli.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                headers=headers,
                params={"fields": "name,mimeType"},
            )
            meta.raise_for_status()
            datos = meta.json()
            cont = cli.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )
            cont.raise_for_status()
        return (
            cont.content,
            datos.get("mimeType", "application/octet-stream"),
            datos.get("name", "archivo"),
        )


drive = GoogleDriveWrapper()

__all__ = [
    "GoogleDriveWrapper",
    "NoConfiguradoError",
    "drive",
    "SCOPES",
    "construir_url_consentimiento",
    "intercambiar_codigo_por_refresh_token",
    "parsear_cliente_json",
    "cliente_configurado",
    "cliente_id_actual",
]
