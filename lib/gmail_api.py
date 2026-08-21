"""Envío de correo por la API de Gmail (HTTPS) — canal de El Cartero.

**Por qué existe.** El Droplet de La Sede tiene bloqueada la salida SMTP:
DigitalOcean descarta los paquetes a los puertos 25, 465, 587 y 2525 (política
antispam), mientras el 443 va perfecto. Se comprobó desde el host y desde el
contenedor. Consecuencia: `smtp.gmail.com` **no es alcanzable** y tampoco lo
sería `smtp-relay.gmail.com` — no es el sabor de SMTP, es que este Droplet no
puede hablar SMTP con nadie. La API de Gmail va por **HTTPS/443**, así que
esquiva el bloqueo sin pedirle nada a DigitalOcean.

**Por qué OAuth con refresh token y NO una cuenta de servicio.** La misma razón
que Drive (ver `docs/SETUP_GOOGLE_DRIVE.md`): la organización de Workspace tiene
activada `iam.disableServiceAccountKeyCreation`, que bloquea la creación de
llaves JSON de cuenta de servicio. Sin llave no hay delegación de dominio, así
que el camino es el mismo patrón de Drive: consentimiento una vez, refresh token
cifrado en La Bóveda, y canje por un access token de corta vida en cada envío.

**Alcance (scope):** `gmail.send` — sólo ENVIAR. No puede leer, buscar ni borrar
correo de nadie. Ojo: Google lo clasifica como scope **sensible**, así que un
cliente OAuth de tipo «Externo» necesita pasar verificación para usarlo. Un
cliente «Interno» (sólo cuentas del Workspace) no la necesita: lo autoriza el
admin de la organización.

**Acoplamiento con el SSO (importante).** Igual que Drive, este canal usa el
cliente OAuth del login (`google_oauth_client_id` / `_secret`). Reemplazar ese
cliente **invalida el refresh token del correo** y hay que volver a conectar
desde el asistente. Está documentado en
`docs/MIGRACION_WORKSPACE_LEARNINGCENTER.md`.

Slots en La Bóveda:
    gmail_api_oauth_refresh_token · gmail_api_remitente
"""

from __future__ import annotations

import base64
import logging
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
# `users/me` = la cuenta que dio el consentimiento.
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
PERFIL_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
HTTP_TIMEOUT = 20.0

SLOT_REFRESH = "gmail_api_oauth_refresh_token"
SLOT_REMITENTE = "gmail_api_remitente"


class GmailApiError(Exception):
    """Base de los errores del módulo."""


class NoConfiguradoError(GmailApiError):
    """Falta el cliente OAuth o el refresh token."""


# ── Credenciales ─────────────────────────────────────────────────────────────


def _credencial(clave: str) -> str | None:
    from ajustes.models.credencial import Credencial
    return Credencial.obtener(clave)


def _cliente_oauth() -> tuple[str, str]:
    """(client_id, client_secret) del cliente OAuth del login con Google."""
    from lib.google_oauth import GoogleOAuthConfig
    cid = GoogleOAuthConfig.client_id()
    sec = GoogleOAuthConfig.client_secret()
    if not cid or not sec:
        raise NoConfiguradoError(
            "Falta el cliente OAuth de Google. Configúralo en Ajustes → "
            "Credenciales (Google OAuth) antes de conectar el correo."
        )
    return cid, sec


def cliente_configurado() -> bool:
    from lib.google_oauth import GoogleOAuthConfig
    return GoogleOAuthConfig.esta_configurado()


def remitente() -> str | None:
    """Dirección desde la que sale el correo (la cuenta que dio consentimiento
    o un alias suyo dado de alta en «Enviar como»)."""
    return _credencial(SLOT_REMITENTE)


def esta_configurado() -> bool:
    """True si el canal puede entregar: cliente OAuth + refresh token + remitente."""
    return bool(cliente_configurado() and _credencial(SLOT_REFRESH) and remitente())


def esta_conectado() -> bool:
    """True si ya hay refresh token (aunque falte definir el remitente)."""
    return bool(cliente_configurado() and _credencial(SLOT_REFRESH))


# ── Consentimiento (una vez, desde el asistente de Ajustes) ──────────────────


def construir_url_consentimiento(redirect_uri: str, state: str) -> str:
    """URL para mandar al navegador del admin.

    `access_type=offline` + `prompt=consent` fuerzan que Google devuelva un
    refresh token también cuando ya se había consentido antes.

    **Sin `include_granted_scopes`** a propósito: acumular scopes haría que este
    token también sirviera para Drive, y se perdería la separación por servicio.
    """
    cid, _ = _cliente_oauth()
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def intercambiar_codigo_por_refresh_token(code: str, redirect_uri: str) -> str:
    """Canjea el `code` del callback por un refresh token. Lo devuelve crudo."""
    cid, sec = _cliente_oauth()
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
            resp = cli.post(TOKEN_URL, data={
                "code": code,
                "client_id": cid,
                "client_secret": sec,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
    except httpx.HTTPError as exc:
        raise NoConfiguradoError(f"No se pudo contactar a Google: {exc}") from exc

    if resp.status_code >= 400:
        detalle = _detalle_error(resp)
        raise NoConfiguradoError(f"Google rechazó el consentimiento: {detalle}")

    refresh = (resp.json() or {}).get("refresh_token")
    if not refresh:
        raise NoConfiguradoError(
            "Google no devolvió un refresh token. Revoca el acceso anterior de "
            "la app en la cuenta de Google y vuelve a conectar."
        )
    return refresh


# ── Envío ────────────────────────────────────────────────────────────────────


def _detalle_error(resp: httpx.Response) -> str:
    try:
        cuerpo = resp.json() or {}
    except Exception:  # noqa: BLE001
        return f"http_{resp.status_code}"
    err = cuerpo.get("error")
    if isinstance(err, dict):
        return err.get("message") or err.get("status") or f"http_{resp.status_code}"
    return str(err or f"http_{resp.status_code}")


def _access_token() -> str:
    """Canjea el refresh token por un access token de corta vida."""
    refresh = _credencial(SLOT_REFRESH)
    if not refresh:
        raise NoConfiguradoError(
            "El correo por Gmail no está conectado. Usa el asistente: "
            "Ajustes → El Cartero → Conectar Gmail."
        )
    cid, sec = _cliente_oauth()
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
            resp = cli.post(TOKEN_URL, data={
                "refresh_token": refresh,
                "client_id": cid,
                "client_secret": sec,
                "grant_type": "refresh_token",
            })
    except httpx.HTTPError as exc:
        raise NoConfiguradoError(f"No se pudo contactar a Google: {exc}") from exc

    if resp.status_code >= 400:
        raise NoConfiguradoError(
            f"El acceso de Google expiró o fue revocado ({_detalle_error(resp)}). "
            "Reconecta desde Ajustes → El Cartero."
        )
    token = (resp.json() or {}).get("access_token")
    if not token:
        raise NoConfiguradoError("Google no devolvió un access token.")
    return token


def enviar_mime(mensaje_bytes: bytes) -> str:
    """Manda un mensaje MIME ya armado. Devuelve el id que asigna Gmail.

    Lanza `GmailApiError` si algo falla — el caller (El Cartero) lo traduce a
    `ResultadoCorreo(ok=False, ...)`.
    """
    token = _access_token()
    # Gmail pide el MIME en base64 **url-safe**; el estándar rompe con `+` y `/`.
    raw = base64.urlsafe_b64encode(mensaje_bytes).decode("ascii")
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
            resp = cli.post(
                SEND_URL,
                headers={"Authorization": f"Bearer {token}"},
                json={"raw": raw},
            )
    except httpx.HTTPError as exc:
        raise GmailApiError(f"No se pudo contactar a Gmail: {exc}") from exc

    if resp.status_code >= 400:
        raise GmailApiError(f"Gmail rechazó el correo: {_detalle_error(resp)}")
    return str((resp.json() or {}).get("id") or "")


def probar() -> dict:
    """Comprueba la conexión leyendo el perfil de la cuenta. No manda correo.

    `gmail.send` NO autoriza leer el perfil, así que un 403 aquí es lo esperado
    y cuenta como éxito: significa que el token es válido y que el scope es el
    mínimo. Lo que sí delata un problema es un 401 (token muerto).
    """
    try:
        token = _access_token()
    except GmailApiError as exc:
        return {"ok": False, "detalle": str(exc)}

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
            resp = cli.get(PERFIL_URL, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        return {"ok": False, "detalle": f"No se pudo contactar a Gmail: {exc}"}

    if resp.status_code == 401:
        return {"ok": False, "detalle": "El token ya no sirve. Reconecta la cuenta."}
    if resp.status_code == 403:
        return {"ok": True, "detalle": "Token válido con el permiso mínimo (sólo enviar)."}
    if resp.status_code >= 400:
        return {"ok": False, "detalle": _detalle_error(resp)}
    correo = (resp.json() or {}).get("emailAddress") or ""
    return {"ok": True, "detalle": f"Conectado como {correo}." if correo else "Token válido."}


__all__ = [
    "SCOPES",
    "SEND_URL",
    "SLOT_REFRESH",
    "SLOT_REMITENTE",
    "GmailApiError",
    "NoConfiguradoError",
    "cliente_configurado",
    "construir_url_consentimiento",
    "enviar_mime",
    "esta_conectado",
    "esta_configurado",
    "intercambiar_codigo_por_refresh_token",
    "probar",
    "remitente",
]
