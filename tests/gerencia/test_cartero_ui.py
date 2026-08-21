"""UI de El Cartero en La Gerencia (/ajustes/cartero/). Solo super_admin."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def test_panel_super_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/ajustes/cartero/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "El Cartero" in body
    assert "SMTP" in body


def test_panel_disenador_sin_acceso(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/ajustes/cartero/")
    assert resp.status_code in (302, 403)


def test_guardar_proveedor_y_smtp(client, usuario_factory):
    from ajustes.models import ConfiguracionCorreo
    from ajustes.models.credencial import Credencial

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cartero/guardar", {
        "proveedor": "smtp",
        "remitente_nombre": "Learning Center",
        "smtp_host": "smtp.example.com",
        "smtp_port": "587",
        "smtp_user": "envia@example.com",
        "smtp_password": "secreta123",
        "smtp_from_email": "envia@example.com",
        "smtp_use_tls": "1",
    })
    assert resp.status_code == 302
    assert ConfiguracionCorreo.obtener().proveedor == "smtp"
    assert Credencial.obtener("smtp_host") == "smtp.example.com"
    assert Credencial.obtener("smtp_password") == "secreta123"


def test_password_vacio_no_borra(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    Credencial.guardar("smtp_password", "guardada")
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    client.post("/ajustes/cartero/guardar", {
        "proveedor": "smtp", "remitente_nombre": "LC",
        "smtp_host": "smtp.example.com", "smtp_from_email": "e@e.com",
        "smtp_password": "",  # vacío → conserva la guardada
    })
    assert Credencial.obtener("smtp_password") == "guardada"


def test_probar_envio(client, usuario_factory, monkeypatch):
    from lib import cartero
    monkeypatch.setattr(
        cartero, "probar",
        lambda destino: cartero.ResultadoCorreo(ok=True, proveedor="smtp", detalle="ok"),
    )
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cartero/probar", {"destinatario": "x@x.com"})
    assert resp.status_code == 302


# ── Canal Gmail API ───────────────────────────────────────────────────────────
#
# El Droplet no puede hablar SMTP (DigitalOcean bloquea 25/465/587/2525), así que
# éste es el canal que de verdad entrega en producción. El asistente sigue el
# patrón del de Drive: consentimiento una vez, refresh token en La Bóveda.


def _cliente_oauth_listo():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_oauth_client_id", "cid.apps.googleusercontent.com")
    Credencial.guardar("google_oauth_client_secret", "secreto")


def test_panel_ofrece_el_canal_gmail_y_avisa_del_bloqueo(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    body = client.get("/ajustes/cartero/").content.decode()

    assert 'value="gmail_api"' in body
    # El panel tiene que decir por qué SMTP no sirve, o alguien lo va a reintentar.
    assert "bloqueada la salida SMTP" in body


def test_conectar_sin_cliente_oauth_avisa(client, usuario_factory):
    """Sin cliente OAuth no hay a dónde mandar al admin: se avisa, no se truena."""
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cartero/gmail/conectar")
    assert resp.status_code == 302
    assert resp["Location"].endswith("/ajustes/cartero/")


def test_conectar_redirige_a_google_con_scope_de_envio(client, usuario_factory):
    _cliente_oauth_listo()
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cartero/gmail/conectar")

    assert resp.status_code == 302
    destino = resp["Location"]
    assert destino.startswith("https://accounts.google.com/")
    assert "gmail.send" in destino
    assert "access_type=offline" in destino


def test_callback_con_state_que_no_coincide_no_guarda_nada(client, usuario_factory):
    """Anti-CSRF: sin el state de la sesión no se acepta el código."""
    from ajustes.models.credencial import Credencial

    _cliente_oauth_listo()
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/ajustes/cartero/gmail/callback", {"code": "x", "state": "inventado"})

    assert resp.status_code == 302
    assert Credencial.obtener("gmail_api_oauth_refresh_token") is None


def test_callback_guarda_el_refresh_token(client, usuario_factory, monkeypatch):
    from ajustes.models.credencial import Credencial
    from lib import gmail_api

    _cliente_oauth_listo()
    u = usuario_factory(rol="super_admin")
    client.force_login(u)

    # Arrancamos el flujo para que el state quede en la sesión.
    client.post("/ajustes/cartero/gmail/conectar")
    state = client.session["gmail_oauth_state"]

    monkeypatch.setattr(
        gmail_api, "intercambiar_codigo_por_refresh_token",
        lambda code, redirect_uri: "1//guardado",
    )
    resp = client.get("/ajustes/cartero/gmail/callback", {"code": "abc", "state": state})

    assert resp.status_code == 302
    assert Credencial.obtener("gmail_api_oauth_refresh_token") == "1//guardado"


def test_guardar_persiste_el_remitente_de_gmail(client, usuario_factory):
    from ajustes.models import ConfiguracionCorreo
    from ajustes.models.credencial import Credencial

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cartero/guardar", {
        "proveedor": "gmail_api",
        "remitente_nombre": "Learning Center",
        "gmail_api_remitente": "hola@learningcenter.mx",
    })

    assert resp.status_code == 302
    assert ConfiguracionCorreo.obtener().proveedor == "gmail_api"
    assert Credencial.obtener("gmail_api_remitente") == "hola@learningcenter.mx"


def test_desconectar_borra_el_token(client, usuario_factory):
    from ajustes.models.credencial import Credencial

    Credencial.guardar("gmail_api_oauth_refresh_token", "1//viejo")
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cartero/gmail/desconectar")

    assert resp.status_code == 302
    assert Credencial.obtener("gmail_api_oauth_refresh_token") is None
