"""Smoke tests del sprint S-UX-Volver para La Gerencia."""

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def _tiene_breadcrumb_o_volver(content: bytes) -> bool:
    return (b'aria-label="Ruta"' in content) or (b"Volver" in content)


def test_directorio_lista(client, usuario_factory):
    u = usuario_factory(rol="super_admin", email="a@x.com")
    client.force_login(u)
    r = client.get("/directorio/")
    assert r.status_code == 200
    assert _tiene_breadcrumb_o_volver(r.content)


def test_ajustes_panel(client, usuario_factory):
    u = usuario_factory(rol="super_admin", email="a@x.com")
    client.force_login(u)
    r = client.get("/ajustes/")
    assert r.status_code == 200
    assert _tiene_breadcrumb_o_volver(r.content)
