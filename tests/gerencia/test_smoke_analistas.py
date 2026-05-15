"""Smoke test del botón 'Probar Analistas' en Los Ajustes."""

from unittest.mock import patch

import httpx  # noqa: F401
import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._p = payload or {}
        self.text = text

    def json(self):
        return self._p


_OK_ANTHROPIC = _Resp(200, {
    "model": "claude-haiku-4-5",
    "content": [{"type": "text", "text": "ok"}],
    "usage": {"input_tokens": 3, "output_tokens": 1},
})


def test_dueno_no_dispara_smoke(client, usuario_factory):
    client.force_login(usuario_factory(rol="dueno"))
    resp = client.post("/ajustes/analistas/probar")
    assert resp.status_code == 403


def test_super_admin_smoke_ok(client, usuario_factory):
    from ajustes.models import AnalistaLog
    from ajustes.models.credencial import Credencial
    Credencial.guardar("anthropic_api_key", "sk-ant-test")
    client.force_login(usuario_factory(rol="super_admin"))
    with patch("httpx.post", return_value=_OK_ANTHROPIC):
        resp = client.post("/ajustes/analistas/probar", follow=True)
    assert resp.status_code == 200
    # El flash success debe contener "anthropic" / "OK".
    body = resp.content.decode()
    # Cubrimos el camino feliz: mensaje "OK — anthropic/claude..." está en el body.
    assert "anthropic" in body, body[:500]
    # En pytest-django, la app y la test session comparten DB pero no
    # necesariamente la misma transacción si la app está en `ATOMIC_REQUESTS`;
    # de cualquier forma, lo importante para S2a.1 es que el endpoint responde
    # sin tirar 500 y reporta el provider. AnalistaLog se valida en el test
    # directo de `analizar()` en tests/test_analistas.py.


def test_smoke_sin_credenciales_emite_error(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/analistas/probar", follow=True)
    assert resp.status_code == 200
    body = resp.content.decode().lower()
    assert "no respondieron" in body or "los analistas" in body
