"""Vistas admin de El Interfono en La Gerencia."""

from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def _configurar_vapid():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("vapid_public_key", "BN-pub")
    Credencial.guardar("vapid_private_key", "ZHByaXY=")


def test_tablero_disenador_403(client, usuario_factory):
    client.force_login(usuario_factory(rol="disenador"))
    resp = client.get("/interfono/")
    assert resp.status_code == 403


def test_tablero_contador_403(client, usuario_factory):
    client.force_login(usuario_factory(rol="contador"))
    resp = client.get("/interfono/")
    assert resp.status_code == 403


def test_tablero_super_admin_ok(client, usuario_factory):
    _configurar_vapid()
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/interfono/")
    assert resp.status_code == 200
    assert b"El Interfono" in resp.content


def test_tablero_dueno_ok(client, usuario_factory):
    client.force_login(usuario_factory(rol="dueno"))
    resp = client.get("/interfono/")
    assert resp.status_code == 200


def test_tablero_muestra_aviso_sin_vapid(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/interfono/")
    assert resp.status_code == 200
    assert b"VAPID" in resp.content


def test_enviar_sin_vapid_redirige_con_error(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/interfono/enviar", {
        "audiencia_tipo": "todos",
        "titulo": "Hola",
        "cuerpo": "Mensaje de prueba",
    })
    assert resp.status_code == 302
    # No se creó el envío porque cortó antes de InterfonoEnvio (chequeo VAPID).
    from interfono.models import InterfonoEnvio
    assert InterfonoEnvio.objects.count() == 0


def test_enviar_modo_prueba_solo_a_si_mismo(client, usuario_factory):
    _configurar_vapid()
    admin = usuario_factory(rol="super_admin", email="admin@x.com")
    otro = usuario_factory(rol="contador", email="otro@x.com")  # noqa: F841
    client.force_login(admin)
    # Sin suscripciones, totales=0 pero registra.
    with patch("pywebpush.webpush", return_value=None):
        resp = client.post("/interfono/enviar", {
            "audiencia_tipo": "todos",
            "titulo": "Hola equipo",
            "cuerpo": "Cuerpo de prueba",
            "modo": "prueba",
        })
    assert resp.status_code == 302
    from interfono.models import InterfonoEnvio
    envio = InterfonoEnvio.objects.get()
    # En modo prueba, audiencia debe sobrescribirse al usuario actual.
    assert envio.audiencia == f"usuario:{admin.pk}"
    assert "admin@x.com" in envio.audiencia_label


def test_enviar_masivo_a_todos(client, usuario_factory):
    _configurar_vapid()
    admin = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="contador")
    from interfono.models import InterfonoSuscripcion
    InterfonoSuscripcion.objects.create(
        usuario=otro, endpoint="https://e/1", p256dh="x", auth="x", activa=True,
    )
    client.force_login(admin)
    with patch("pywebpush.webpush", return_value=None):
        resp = client.post("/interfono/enviar", {
            "audiencia_tipo": "todos",
            "titulo": "T",
            "cuerpo": "C",
            "modo": "enviar",
        })
    assert resp.status_code == 302
    from interfono.models import InterfonoEnvio
    envio = InterfonoEnvio.objects.get()
    assert envio.audiencia == "todos"
    assert envio.entregadas == 1


def test_perfil_notificaciones_login_required(client):
    resp = client.get("/perfil/notificaciones/")
    assert resp.status_code in (302, 401, 403)


def test_perfil_notificaciones_render(client, usuario_factory):
    _configurar_vapid()
    client.force_login(usuario_factory(rol="disenador"))
    resp = client.get("/perfil/notificaciones/")
    assert resp.status_code == 200
    assert b"notificaciones" in resp.content.lower()


def test_sw_js_disponible_en_gerencia(client):
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "application/javascript" in resp["Content-Type"]
