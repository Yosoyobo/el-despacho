"""Cliente Google OAuth — lee credenciales de Los Ajustes (La Bóveda).

Scopes mínimos (openid + email + profile). El `redirect_uri` se construye
dinámicamente desde la `request` en cada flow, de modo que los 3 hosts
(gerencia/taller/recepcion) pueden compartir el mismo OAuth Client.

Si las credenciales no están configuradas, las funciones lanzan
`GoogleOAuthNoConfigurado` (subclase de `GoogleOAuthError`). El context
processor `google_oauth_configurado` permite que el botón "Continuar con
Google" se oculte cuando no hay credenciales — sin botones rotos.
"""

from __future__ import annotations

import contextlib
import logging
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = ["openid", "email", "profile"]
HTTP_TIMEOUT = 5.0


# ── Excepciones ──────────────────────────────────────────────────────────────


class GoogleOAuthError(Exception):
    """Base de todos los errores del módulo."""


class GoogleOAuthNoConfigurado(GoogleOAuthError):
    """Faltan credenciales (client_id/client_secret) en La Bóveda."""


class GoogleOAuthCodigoInvalido(GoogleOAuthError):
    """Google rechazó el `code` durante el intercambio (`invalid_grant`, etc.)."""


class GoogleOAuthCuentaNoRegistrada(GoogleOAuthError):
    """El email de Google no matchea con ningún Usuario activo en El Directorio."""

    def __init__(self, email: str):
        super().__init__(email)
        self.email = email


class GoogleOAuthYaVinculadoAOtra(GoogleOAuthError):
    """El Usuario tiene `google_sub` ya asignado a OTRA cuenta Google."""

    def __init__(self, email: str):
        super().__init__(email)
        self.email = email


# ── Perfil ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PerfilGoogle:
    sub: str
    email: str
    email_verified: bool
    nombre: str
    apellido: str
    foto_url: str | None
    locale: str | None

    @property
    def nombre_completo(self) -> str:
        partes = [p for p in (self.nombre, self.apellido) if p]
        return " ".join(partes) or self.email


# ── Config ───────────────────────────────────────────────────────────────────


class GoogleOAuthConfig:
    """Lee credenciales de La Bóveda. Cero hardcode."""

    @classmethod
    def client_id(cls) -> str | None:
        from ajustes.models.credencial import Credencial
        return Credencial.obtener("google_oauth_client_id")

    @classmethod
    def client_secret(cls) -> str | None:
        from ajustes.models.credencial import Credencial
        return Credencial.obtener("google_oauth_client_secret")

    @classmethod
    def project_id(cls) -> str | None:
        from ajustes.models.credencial import Credencial
        return Credencial.obtener("google_oauth_project_id")

    @classmethod
    def esta_configurado(cls) -> bool:
        return bool(cls.client_id() and cls.client_secret())


def _exigir_configurado() -> tuple[str, str]:
    cid = GoogleOAuthConfig.client_id()
    sec = GoogleOAuthConfig.client_secret()
    if not cid or not sec:
        raise GoogleOAuthNoConfigurado("Credenciales OAuth no configuradas en Los Ajustes.")
    return cid, sec


# ── Flow ─────────────────────────────────────────────────────────────────────


def construir_url_autorizacion(redirect_uri: str, state: str, nonce: str) -> str:
    """URL para enviar al navegador del usuario. Anti-CSRF con `state` + `nonce`."""
    cid, _ = _exigir_configurado()
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "online",
        "prompt": "select_account",
        "state": state,
        "nonce": nonce,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def generar_state_nonce() -> tuple[str, str]:
    return secrets.token_urlsafe(24), secrets.token_urlsafe(24)


def intercambiar_codigo_por_perfil(code: str, redirect_uri: str) -> PerfilGoogle:
    """POST token + GET userinfo. Lanza GoogleOAuthCodigoInvalido si Google rechaza."""
    cid, sec = _exigir_configurado()
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
            tok = cli.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": cid,
                    "client_secret": sec,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if tok.status_code >= 400:
                detalle = (tok.json() or {}).get("error", f"http_{tok.status_code}")
                raise GoogleOAuthCodigoInvalido(f"Google rechazó el code: {detalle}")
            access = tok.json()["access_token"]
            info = cli.get(USERINFO_URL, headers={"Authorization": f"Bearer {access}"})
            info.raise_for_status()
            data = info.json()
    except httpx.HTTPError as exc:
        raise GoogleOAuthCodigoInvalido(f"Red caída hacia Google: {exc}") from exc

    return PerfilGoogle(
        sub=data["sub"],
        email=data["email"],
        email_verified=bool(data.get("email_verified", False)),
        nombre=data.get("given_name", "") or data.get("name", ""),
        apellido=data.get("family_name", ""),
        foto_url=data.get("picture"),
        locale=data.get("locale"),
    )


# ── Diagnóstico ──────────────────────────────────────────────────────────────


def probar_conexion() -> dict:
    """Valida las credenciales con un POST al endpoint de token con `code` dummy.

    Heurística:
    - `invalid_grant`  → credenciales OK, solo el code es inválido (esperado)
    - `invalid_client` → credenciales mal (client_id/secret incorrectos)
    - cualquier otra cosa → reportar tal cual

    Retorna {"ok": bool, "detalle": str}.
    """
    try:
        cid, sec = _exigir_configurado()
    except GoogleOAuthNoConfigurado as exc:
        return {"ok": False, "detalle": str(exc)}

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as cli:
            resp = cli.post(
                TOKEN_URL,
                data={
                    "client_id": cid,
                    "client_secret": sec,
                    "code": "dummy-validacion-credenciales",
                    "grant_type": "authorization_code",
                    "redirect_uri": "https://example.invalid/callback",
                },
            )
    except httpx.HTTPError as exc:
        return {"ok": False, "detalle": f"Red caída hacia Google: {exc}"}

    body = {}
    with contextlib.suppress(Exception):
        body = resp.json()
    error = body.get("error", "")

    if error == "invalid_grant":
        return {"ok": True, "detalle": "Credenciales válidas (Google rechazó el code dummy, lo esperado)."}
    if error == "invalid_client":
        return {"ok": False, "detalle": "client_id o client_secret incorrectos."}
    return {"ok": False, "detalle": f"Respuesta inesperada: HTTP {resp.status_code} {error or body}"}


# ── Helper: redirect_uri dinámico ────────────────────────────────────────────


def redirect_uri_desde_request(request) -> str:
    """Construye el redirect_uri canónico del host actual.

    En producción detrás de Caddy, `request.scheme` ya es 'https' gracias a
    `SECURE_PROXY_SSL_HEADER`. En HAL local devuelve 'http' — debe estar
    registrado el `http://localhost:PORT/auth/google/callback` en Cloud Console.
    """
    return f"{request.scheme}://{request.get_host()}/auth/google/callback"
