"""Cliente Google OAuth — lee credenciales desde Los Ajustes (Bóveda).

Si las credenciales no están configuradas, las funciones devuelven 503-graceful
(no levantan excepción no manejada). El botón "Entrar con Google" debe verificar
`esta_configurado()` antes de mostrarse activo.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import httpx

from .errors import CredencialFaltante

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = ["openid", "email", "profile"]


@dataclass
class GooglePerfil:
    email: str
    nombre: str
    avatar_url: str | None
    google_sub: str


def _leer_credenciales():
    """Devuelve (client_id, client_secret, redirect_uri) o lanza CredencialFaltante."""
    from ajustes.models.credencial import Credencial

    cid = Credencial.obtener("google_oauth_client_id")
    sec = Credencial.obtener("google_oauth_client_secret")
    redir = Credencial.obtener("google_oauth_redirect_uri")
    if not cid or not sec or not redir:
        raise CredencialFaltante("google_oauth")
    return cid, sec, redir


def esta_configurado() -> bool:
    try:
        _leer_credenciales()
        return True
    except Exception:
        return False


def url_autorizacion(state: Optional[str] = None) -> tuple[str, str]:
    cid, _, redir = _leer_credenciales()
    state = state or secrets.token_urlsafe(24)
    params = {
        "client_id": cid,
        "redirect_uri": redir,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "online",
        "prompt": "select_account",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}", state


def intercambiar_code(code: str) -> GooglePerfil:
    cid, sec, redir = _leer_credenciales()
    with httpx.Client(timeout=10.0) as cli:
        tok = cli.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": cid,
                "client_secret": sec,
                "redirect_uri": redir,
                "grant_type": "authorization_code",
            },
        )
        tok.raise_for_status()
        access = tok.json()["access_token"]
        info = cli.get(USERINFO_URL, headers={"Authorization": f"Bearer {access}"})
        info.raise_for_status()
        data = info.json()
    return GooglePerfil(
        email=data["email"],
        nombre=data.get("name", ""),
        avatar_url=data.get("picture"),
        google_sub=data["sub"],
    )
