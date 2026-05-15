"""Integración: el botón aparece/desaparece según `google_oauth_configurado`."""

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_sign_in_taller_sin_credenciales_no_muestra_boton(client):
    resp = client.get("/sign-in")
    assert resp.status_code == 200
    assert b"Continuar con Google" not in resp.content


def test_sign_in_taller_con_credenciales_muestra_boton(client):
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_oauth_client_id", "abc.apps.googleusercontent.com")
    Credencial.guardar("google_oauth_client_secret", "GOCSPX-x")
    resp = client.get("/sign-in")
    assert resp.status_code == 200
    assert b"Continuar con Google" in resp.content
    assert b"/auth/google/iniciar" in resp.content


def test_sign_in_taller_boton_apunta_a_iniciar(client):
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_oauth_client_id", "abc.apps.googleusercontent.com")
    Credencial.guardar("google_oauth_client_secret", "GOCSPX-x")
    resp = client.get("/sign-in")
    assert b'href="/auth/google/iniciar"' in resp.content
