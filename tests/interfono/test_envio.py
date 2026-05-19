"""Pruebas de envío con pywebpush mockeado."""

from __future__ import annotations

from unittest.mock import patch  # noqa: I001

import pytest

pytestmark = pytest.mark.django_db


def _crear_sub(usuario_factory, **kwargs):
    from interfono.models import InterfonoSuscripcion
    defaults = {
        "usuario": kwargs.pop("usuario", None) or usuario_factory(),
        "endpoint": kwargs.pop("endpoint", "https://fcm.googleapis.com/fcm/send/xyz"),
        "p256dh": "BN-publica",
        "auth": "auth-secret",
        "user_agent": "test",
    }
    defaults.update(kwargs)
    return InterfonoSuscripcion.objects.create(**defaults)


def _configurar_vapid():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("vapid_public_key", "BNpublica-prueba")
    Credencial.guardar("vapid_private_key", "ZHByaXZhZGEtcHJ1ZWJh")
    Credencial.guardar("vapid_email", "mailto:test@ejemplo.com")


class _FakeResp:
    def __init__(self, status_code):
        self.status_code = status_code


def test_no_configurado_devuelve_temprano(usuario_factory):
    sub = _crear_sub(usuario_factory)
    from lib.interfono import enviar_a_suscripcion
    assert enviar_a_suscripcion(sub, "t", "c") == "no_configurado"


def test_envio_ok(usuario_factory):
    _configurar_vapid()
    sub = _crear_sub(usuario_factory)
    with patch("pywebpush.webpush", return_value=None):
        from lib.interfono import enviar_a_suscripcion
        assert enviar_a_suscripcion(sub, "t", "c") == "ok"


def test_envio_expired_invalida(usuario_factory):
    _configurar_vapid()
    sub = _crear_sub(usuario_factory)
    from pywebpush import WebPushException

    exc = WebPushException("gone")
    exc.response = _FakeResp(410)
    with patch("pywebpush.webpush", side_effect=exc):
        from lib.interfono import enviar_a_suscripcion
        assert enviar_a_suscripcion(sub, "t", "c") == "expired"
    sub.refresh_from_db()
    assert sub.activa is False
    assert sub.desactivada_en is not None


def test_envio_error_transitorio_no_invalida(usuario_factory):
    _configurar_vapid()
    sub = _crear_sub(usuario_factory)
    from pywebpush import WebPushException

    exc = WebPushException("boom")
    exc.response = _FakeResp(500)
    with patch("pywebpush.webpush", side_effect=exc):
        from lib.interfono import enviar_a_suscripcion
        assert enviar_a_suscripcion(sub, "t", "c") == "error"
    sub.refresh_from_db()
    assert sub.activa is True


def test_enviar_a_usuario_agrega_totales(usuario_factory):
    _configurar_vapid()
    u = usuario_factory()
    _crear_sub(usuario_factory, usuario=u, endpoint="https://e1")
    _crear_sub(usuario_factory, usuario=u, endpoint="https://e2")

    with patch("pywebpush.webpush", return_value=None):
        from lib.interfono import enviar_a_usuario
        totales = enviar_a_usuario(u, "t", "c")
    assert totales["entregadas"] == 2
    assert totales["fallidas"] == 0
    assert totales["invalidadas"] == 0
    assert totales["entrega_id"] > 0


def test_enviar_a_usuario_mezcla_ok_expired(usuario_factory):
    _configurar_vapid()
    u = usuario_factory()
    s_ok = _crear_sub(usuario_factory, usuario=u, endpoint="https://ok")
    s_exp = _crear_sub(usuario_factory, usuario=u, endpoint="https://exp")
    from pywebpush import WebPushException

    exc = WebPushException("gone")
    exc.response = _FakeResp(404)

    def fake_webpush(**kwargs):
        if "exp" in kwargs["subscription_info"]["endpoint"]:
            raise exc
        return None

    with patch("pywebpush.webpush", side_effect=fake_webpush):
        from lib.interfono import enviar_a_usuario
        totales = enviar_a_usuario(u, "t", "c")
    assert totales["entregadas"] == 1
    assert totales["invalidadas"] == 1
    s_exp.refresh_from_db()
    s_ok.refresh_from_db()
    assert s_exp.activa is False
    assert s_ok.activa is True
