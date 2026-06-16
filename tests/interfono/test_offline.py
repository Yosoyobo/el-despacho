"""Página offline dedicada (/offline/) + su precache en el service worker."""

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_offline_publica_sin_login(client):
    resp = client.get("/offline/")
    assert resp.status_code == 200
    assert "text/html" in resp["Content-Type"]
    body = resp.content.decode()
    assert "Sin conexión" in body
    # Logo inyectado (resuelto con static, no el placeholder crudo).
    assert "__LOGO__" not in body
    assert "Reintentar" in body


def test_sw_precachea_offline(client):
    body = client.get("/sw.js").content.decode()
    assert 'DESPACHO_OFFLINE = "/offline/"' in body
    assert "/offline/" in body  # también en la lista de precache
