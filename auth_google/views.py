"""Views compartidas del SSO de Google.

`iniciar`: arma URL de autorización + state/nonce en sesión + redirect.
`callback`: valida state, intercambia code por perfil, register-or-link,
            login y redirect a home (o al `next` original).
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth import login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from lib.google_oauth import (
    GoogleOAuthCodigoInvalido,
    GoogleOAuthConfig,
    GoogleOAuthCuentaNoRegistrada,
    GoogleOAuthError,
    GoogleOAuthYaVinculadoAOtra,
    construir_url_autorizacion,
    generar_state_nonce,
    intercambiar_codigo_por_perfil,
    redirect_uri_desde_request,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .servicios import register_or_link_google_user

logger = logging.getLogger(__name__)

SESSION_STATE = "_google_oauth_state"
SESSION_NONCE = "_google_oauth_nonce"
SESSION_NEXT = "_google_oauth_next"


def iniciar(request: HttpRequest) -> HttpResponse:
    if not GoogleOAuthConfig.esta_configurado():
        messages.error(request, "SSO de Google no configurado. Contacta al administrador.")
        return redirect("/sign-in")

    state, nonce = generar_state_nonce()
    request.session[SESSION_STATE] = state
    request.session[SESSION_NONCE] = nonce

    nxt = request.GET.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=False):
        request.session[SESSION_NEXT] = nxt

    redirect_uri = redirect_uri_desde_request(request)
    url = construir_url_autorizacion(redirect_uri, state=state, nonce=nonce)
    return redirect(url)


def callback(request: HttpRequest) -> HttpResponse:
    if request.GET.get("error"):
        return _render_error(request, motivo="acceso_denegado", detalle=request.GET.get("error", ""))

    code = request.GET.get("code", "")
    state = request.GET.get("state", "")
    state_esperado = request.session.pop(SESSION_STATE, None)
    request.session.pop(SESSION_NONCE, None)
    nxt = request.session.pop(SESSION_NEXT, "")

    if not code or not state or state != state_esperado:
        return _render_error(request, motivo="state_invalido", status=400)

    redirect_uri = redirect_uri_desde_request(request)

    try:
        perfil = intercambiar_codigo_por_perfil(code, redirect_uri)
    except GoogleOAuthCodigoInvalido as exc:
        _emitir_error("codigo_invalido", str(exc), request)
        return _render_error(request, motivo="codigo_invalido", status=400)

    try:
        usuario = register_or_link_google_user(perfil)
    except GoogleOAuthCuentaNoRegistrada as exc:
        return _render_error(request, motivo="cuenta_no_registrada", email_google=exc.email, status=403)
    except GoogleOAuthYaVinculadoAOtra as exc:
        return _render_error(request, motivo="ya_vinculado", email_google=exc.email, status=409)
    except GoogleOAuthError as exc:
        _emitir_error("desconocido", str(exc), request)
        return _render_error(request, motivo="desconocido", status=500)

    if not _host_permite_rol(request.get_host(), usuario.rol):
        return _render_error(request, motivo="rol_no_permitido", email_google=perfil.email, status=403)

    usuario.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, usuario)
    destino = nxt or "/"
    return redirect(destino)


def _host_permite_rol(host: str, rol: str) -> bool:
    """La Gerencia es solo para super_admin/dueno. El Taller acepta los 4 roles."""
    if "gerencia" in host:
        return rol in ("super_admin", "dueno")
    return True


def _render_error(request, *, motivo: str, detalle: str = "", email_google: str = "", status: int = 400):
    return render(request, "auth_google/error.html", {
        "motivo": motivo,
        "detalle": detalle,
        "email_google": email_google,
    }, status=status)


def _emitir_error(tipo: str, mensaje: str, request) -> None:
    try:
        emitir(EventoPortavoz(
            tipo="auth.google_error",
            actor_id=None,
            actor_email=None,
            payload={
                "tipo_error": tipo,
                "mensaje": mensaje[:300],
                "ip_origen": request.META.get("REMOTE_ADDR", ""),
            },
        ))
    except Exception:
        logger.warning("portavoz: no se pudo emitir auth.google_error", exc_info=True)
