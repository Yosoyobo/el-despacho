"""Pruebas de `lib/google_oauth.py` con httpx mockeado."""

from unittest.mock import patch

import httpx
import pytest

pytestmark = pytest.mark.django_db


def _configurar():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_oauth_client_id", "abc.apps.googleusercontent.com")
    Credencial.guardar("google_oauth_client_secret", "GOCSPX-prueba")


def test_esta_configurado_falso_sin_credenciales():
    from lib.google_oauth import GoogleOAuthConfig
    assert GoogleOAuthConfig.esta_configurado() is False


def test_esta_configurado_verdadero_con_credenciales():
    _configurar()
    from lib.google_oauth import GoogleOAuthConfig
    assert GoogleOAuthConfig.esta_configurado() is True


def test_construir_url_autorizacion_incluye_params():
    _configurar()
    from lib.google_oauth import construir_url_autorizacion
    url = construir_url_autorizacion("https://taller.ejemplo/auth/google/callback", state="S", nonce="N")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=abc.apps.googleusercontent.com" in url
    assert "redirect_uri=https%3A%2F%2Ftaller.ejemplo%2Fauth%2Fgoogle%2Fcallback" in url
    assert "state=S" in url and "nonce=N" in url
    assert "scope=openid+email+profile" in url
    assert "response_type=code" in url


def test_construir_url_sin_credenciales_levanta():
    from lib.google_oauth import GoogleOAuthNoConfigurado, construir_url_autorizacion
    with pytest.raises(GoogleOAuthNoConfigurado):
        construir_url_autorizacion("https://x/cb", state="s", nonce="n")


def _mock_httpx(post_resp=None, get_resp=None):
    """Devuelve un context manager que parchea httpx.Client.{post,get}."""

    class _FakeResp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("err", request=None, response=self)

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, data=None):
            return post_resp

        def get(self, url, headers=None):
            return get_resp

    return patch("lib.google_oauth.httpx.Client", _FakeClient), _FakeResp


def test_intercambiar_codigo_ok():
    _configurar()
    from lib.google_oauth import intercambiar_codigo_por_perfil

    class R:
        status_code = 200
        def json(self): return {"access_token": "ya29.x", "id_token": "x"}
        def raise_for_status(self): pass

    class U:
        status_code = 200
        def json(self):
            return {
                "sub": "12345",
                "email": "oscar@bautista.mx",
                "email_verified": True,
                "given_name": "Oscar",
                "family_name": "Bautista",
                "picture": "https://x/foto.jpg",
                "locale": "es-MX",
            }
        def raise_for_status(self): pass

    cm, _ = _mock_httpx(post_resp=R(), get_resp=U())
    with cm:
        perfil = intercambiar_codigo_por_perfil("code-xyz", "https://x/cb")
    assert perfil.sub == "12345"
    assert perfil.email == "oscar@bautista.mx"
    assert perfil.email_verified is True
    assert perfil.nombre_completo == "Oscar Bautista"


def test_intercambiar_codigo_rechazado():
    _configurar()
    from lib.google_oauth import GoogleOAuthCodigoInvalido, intercambiar_codigo_por_perfil

    class R:
        status_code = 400
        def json(self): return {"error": "invalid_grant"}
        def raise_for_status(self): raise httpx.HTTPStatusError("e", request=None, response=self)

    cm, _ = _mock_httpx(post_resp=R(), get_resp=None)
    with cm, pytest.raises(GoogleOAuthCodigoInvalido) as ei:
        intercambiar_codigo_por_perfil("code-bad", "https://x/cb")
    assert "invalid_grant" in str(ei.value)


def test_probar_conexion_ok():
    _configurar()
    from lib.google_oauth import probar_conexion

    class R:
        status_code = 400
        def json(self): return {"error": "invalid_grant"}

    cm, _ = _mock_httpx(post_resp=R())
    with cm:
        res = probar_conexion()
    assert res["ok"] is True


def test_probar_conexion_client_mal():
    _configurar()
    from lib.google_oauth import probar_conexion

    class R:
        status_code = 401
        def json(self): return {"error": "invalid_client"}

    cm, _ = _mock_httpx(post_resp=R())
    with cm:
        res = probar_conexion()
    assert res["ok"] is False
    assert "client_id" in res["detalle"].lower() or "secret" in res["detalle"].lower()


def test_probar_conexion_sin_credenciales():
    from lib.google_oauth import probar_conexion
    res = probar_conexion()
    assert res["ok"] is False


def test_redirect_uri_desde_request():
    from lib.google_oauth import redirect_uri_desde_request

    class R:
        scheme = "https"
        def get_host(self): return "taller.ninomeando.com"

    assert redirect_uri_desde_request(R()) == "https://taller.ninomeando.com/auth/google/callback"
