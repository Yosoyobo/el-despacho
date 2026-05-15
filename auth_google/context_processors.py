"""Inyecta `google_oauth_configurado` (bool) en todos los templates."""

from __future__ import annotations


def google_oauth_configurado(request) -> dict:
    try:
        from lib.google_oauth import GoogleOAuthConfig
        return {"google_oauth_configurado": GoogleOAuthConfig.esta_configurado()}
    except Exception:
        return {"google_oauth_configurado": False}
