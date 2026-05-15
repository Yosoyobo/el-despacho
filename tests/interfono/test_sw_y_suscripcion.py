"""Endpoint /sw.js + /perfil/notificaciones/suscribir."""

import json
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_sw_js_publico(client):
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "application/javascript" in resp["Content-Type"]
    assert resp["Service-Worker-Allowed"] == "/"
    body = resp.content.decode()
    assert "self.addEventListener('push'" in body
    assert "el-despacho-" in body  # tag default único


def test_suscribir_requiere_login(client):
    resp = client.post(
        "/perfil/notificaciones/suscribir",
        data=json.dumps({"endpoint": "https://e", "keys": {"p256dh": "p", "auth": "a"}}),
        content_type="application/json",
    )
    assert resp.status_code in (302, 401, 403)


def test_suscribir_crea_fila(client, usuario_factory):
    u = usuario_factory()
    client.force_login(u)
    resp = client.post(
        "/perfil/notificaciones/suscribir",
        data=json.dumps({"endpoint": "https://fcm.googleapis.com/x", "keys": {"p256dh": "p256", "auth": "auth-x"}}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    from interfono.models import InterfonoSuscripcion
    sub = InterfonoSuscripcion.objects.get(endpoint="https://fcm.googleapis.com/x")
    assert sub.usuario_id == u.pk
    assert sub.p256dh == "p256"
    assert sub.auth == "auth-x"
    assert sub.activa is True


def test_suscribir_idempotente_reactiva(client, usuario_factory):
    u = usuario_factory()
    client.force_login(u)
    from django.utils import timezone

    from interfono.models import InterfonoSuscripcion

    InterfonoSuscripcion.objects.create(
        usuario=u, endpoint="https://e/y", p256dh="old", auth="old",
        activa=False, desactivada_en=timezone.now(),
    )
    resp = client.post(
        "/perfil/notificaciones/suscribir",
        data=json.dumps({"endpoint": "https://e/y", "keys": {"p256dh": "nuevo", "auth": "nuevo"}}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    sub = InterfonoSuscripcion.objects.get(endpoint="https://e/y")
    assert sub.activa is True
    assert sub.desactivada_en is None
    assert sub.p256dh == "nuevo"


def test_suscribir_payload_invalido(client, usuario_factory):
    client.force_login(usuario_factory())
    resp = client.post("/perfil/notificaciones/suscribir", data="{}", content_type="application/json")
    assert resp.status_code == 400


def test_desuscribir(client, usuario_factory):
    u = usuario_factory()
    client.force_login(u)
    from interfono.models import InterfonoSuscripcion
    sub = InterfonoSuscripcion.objects.create(
        usuario=u, endpoint="https://e/d", p256dh="x", auth="x", activa=True,
    )
    resp = client.post(f"/perfil/notificaciones/{sub.pk}/desuscribir")
    assert resp.status_code == 200
    sub.refresh_from_db()
    assert sub.activa is False


def test_desuscribir_ajeno_404(client, usuario_factory):
    u1 = usuario_factory()
    u2 = usuario_factory()
    from interfono.models import InterfonoSuscripcion
    sub = InterfonoSuscripcion.objects.create(
        usuario=u1, endpoint="https://e/z", p256dh="x", auth="x", activa=True,
    )
    client.force_login(u2)
    resp = client.post(f"/perfil/notificaciones/{sub.pk}/desuscribir")
    assert resp.status_code == 404


def test_prueba_sin_vapid_503(client, usuario_factory):
    client.force_login(usuario_factory())
    resp = client.post("/perfil/notificaciones/prueba")
    assert resp.status_code == 503


def test_prueba_con_vapid_ok(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    Credencial.guardar("vapid_public_key", "BNpub")
    Credencial.guardar("vapid_private_key", "ZHByaXY=")
    u = usuario_factory()
    client.force_login(u)
    # Sin suscripciones, totales=0 pero responde 200.
    with patch("pywebpush.webpush", return_value=None):
        resp = client.post("/perfil/notificaciones/prueba")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entregadas"] == 0
