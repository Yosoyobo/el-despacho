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
