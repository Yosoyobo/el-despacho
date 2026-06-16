"""Auditoría de Chalanes: columna 'Quién' + detalle clickeable (hash-only)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def _log(actor=None, **kw):
    from ajustes.models.analistas_log import AnalistaLog
    defaults = dict(
        estacion="taller_chat", provider="anthropic", modelo="claude-haiku-4-5",
        prompt_hash="abc123", prompt_tokens=120, completion_tokens=40,
        latencia_ms=2999, exito=True, actor=actor,
    )
    defaults.update(kw)
    return AnalistaLog.objects.create(**defaults)


def test_panel_muestra_quien(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    _log(actor=admin)
    client.force_login(admin)
    resp = client.get("/chalanes/")
    assert resp.status_code == 200
    assert b"Qui\xc3\xa9n" in resp.content  # encabezado "Quién"


def test_detalle_auditoria_super_admin(client, usuario_factory):
    admin = usuario_factory(rol="super_admin", email="jefe@lc.mx")
    log = _log(actor=admin)
    client.force_login(admin)
    resp = client.get(f"/chalanes/auditoria/{log.pk}/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Detalle del intento" in body
    assert "jefe@lc.mx" in body          # quién
    assert "2999 ms" in body             # tiempo de respuesta
    assert "claude-haiku-4-5" in body    # modelo
    # Hash-only: no se filtra texto del prompt, solo el hash.
    assert "abc123" in body


def test_detalle_auditoria_disenador_sin_acceso(client, usuario_factory):
    log = _log()
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get(f"/chalanes/auditoria/{log.pk}/")
    assert resp.status_code in (302, 403)
