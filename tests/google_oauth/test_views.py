"""Pruebas de las views iniciar/callback con httpx mockeado."""

from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _configurar():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_oauth_client_id", "abc.apps.googleusercontent.com")
    Credencial.guardar("google_oauth_client_secret", "GOCSPX-prueba")


def test_iniciar_sin_credenciales_redirige_login(client):
    resp = client.get("/auth/google/iniciar")
    assert resp.status_code == 302
    assert resp["Location"] == "/sign-in"


def test_iniciar_con_credenciales_redirige_a_google(client):
    _configurar()
    resp = client.get("/auth/google/iniciar")
    assert resp.status_code == 302
    assert resp["Location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=abc.apps.googleusercontent.com" in resp["Location"]
    # session debe tener state guardado
    assert client.session.get("_google_oauth_state")


def test_callback_state_mismatch(client):
    _configurar()
    # primero iniciar para establecer state
    client.get("/auth/google/iniciar")
    resp = client.get("/auth/google/callback", {"code": "x", "state": "estado-falso"})
    assert resp.status_code == 400
    assert b"sesi\xc3\xb3n" in resp.content.lower() or b"sesion" in resp.content.lower()


def _mock_intercambio(perfil_kwargs):
    from lib.google_oauth import PerfilGoogle
    perfil = PerfilGoogle(
        sub=perfil_kwargs.get("sub", "g-99"),
        email=perfil_kwargs.get("email", "oscar@bautista.mx"),
        email_verified=True,
        nombre=perfil_kwargs.get("nombre", "Oscar"),
        apellido="",
        foto_url=None,
        locale=None,
    )
    return patch("auth_google.views.intercambiar_codigo_por_perfil", return_value=perfil)


def test_callback_exitoso_loguea_y_redirige_home(client, usuario_factory):
    _configurar()
    usuario_factory(rol="disenador", email="oscar@bautista.mx")
    iniciar_resp = client.get("/auth/google/iniciar")
    state = client.session.get("_google_oauth_state")
    assert state and iniciar_resp.status_code == 302

    with _mock_intercambio({"email": "oscar@bautista.mx"}):
        resp = client.get("/auth/google/callback", {"code": "good", "state": state})
    assert resp.status_code == 302
    assert resp["Location"] == "/"


def test_callback_email_no_registrado_renderiza_error(client):
    _configurar()
    client.get("/auth/google/iniciar")
    state = client.session.get("_google_oauth_state")
    with _mock_intercambio({"email": "desconocido@xyz.com"}):
        resp = client.get("/auth/google/callback", {"code": "good", "state": state})
    assert resp.status_code == 403
    assert b"desconocido@xyz.com" in resp.content


def test_callback_acceso_denegado(client):
    _configurar()
    resp = client.get("/auth/google/callback", {"error": "access_denied"})
    assert resp.status_code == 400
    assert b"autorizaste" in resp.content.lower() or b"google" in resp.content.lower()


def test_callback_codigo_invalido_renderiza_error(client):
    _configurar()
    client.get("/auth/google/iniciar")
    state = client.session.get("_google_oauth_state")
    from lib.google_oauth import GoogleOAuthCodigoInvalido
    with patch("auth_google.views.intercambiar_codigo_por_perfil", side_effect=GoogleOAuthCodigoInvalido("boom")):
        resp = client.get("/auth/google/callback", {"code": "bad", "state": state})
    assert resp.status_code == 400


def test_callback_respeta_next_seguro(client, usuario_factory):
    _configurar()
    usuario_factory(rol="contador", email="ana@x.com")
    resp_iniciar = client.get("/auth/google/iniciar", {"next": "/proyectos/"})
    state = client.session.get("_google_oauth_state")
    assert state and resp_iniciar.status_code == 302

    with _mock_intercambio({"email": "ana@x.com"}):
        resp = client.get("/auth/google/callback", {"code": "good", "state": state})
    assert resp.status_code == 302
    assert resp["Location"] == "/proyectos/"


def test_callback_descarta_next_externo(client, usuario_factory):
    _configurar()
    usuario_factory(rol="contador", email="ana@x.com")
    client.get("/auth/google/iniciar", {"next": "https://evil.example/phish"})
    state = client.session.get("_google_oauth_state")
    with _mock_intercambio({"email": "ana@x.com"}):
        resp = client.get("/auth/google/callback", {"code": "good", "state": state})
    assert resp.status_code == 302
    assert resp["Location"] == "/"  # next externo ignorado
