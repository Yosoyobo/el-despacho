"""Smoke tests para lib/google_oauth — flujo real OAuth no se mockea (S2+)."""

from unittest.mock import patch

from lib import google_oauth


def test_esta_configurado_false_sin_credenciales():
    with patch.object(google_oauth, "_leer_credenciales", side_effect=Exception("no creds")):
        assert google_oauth.esta_configurado() is False


def test_esta_configurado_true_con_credenciales():
    with patch.object(google_oauth, "_leer_credenciales", return_value=("cid", "secret", "https://x/cb")):
        assert google_oauth.esta_configurado() is True


def test_url_autorizacion_arma_query():
    with patch.object(google_oauth, "_leer_credenciales", return_value=("cid", "secret", "https://x/cb")):
        url, state = google_oauth.url_autorizacion()
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "client_id=cid" in url
        assert "redirect_uri=" in url
        assert "response_type=code" in url
        assert state and isinstance(state, str)


def test_url_autorizacion_respeta_state_provisto():
    with patch.object(google_oauth, "_leer_credenciales", return_value=("cid", "secret", "https://x/cb")):
        url, state = google_oauth.url_autorizacion(state="abcdef")
        assert state == "abcdef"
        assert "state=abcdef" in url
