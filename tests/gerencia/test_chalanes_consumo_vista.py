"""S-Chalanes-Consumo: página de analítica en La Gerencia con selector de ventana."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def test_consumo_super_admin(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/chalanes/consumo/")
    assert resp.status_code == 200
    assert b"Consumo de IA" in resp.content
    assert resp.context["ventana"] == 30


def test_consumo_ventana_valida(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    assert client.get("/chalanes/consumo/?ventana=7").context["ventana"] == 7
    assert client.get("/chalanes/consumo/?ventana=90").context["ventana"] == 90
    # Inválida cae a 30.
    assert client.get("/chalanes/consumo/?ventana=999").context["ventana"] == 30


def test_consumo_disenador_sin_acceso(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/chalanes/consumo/")
    assert resp.status_code in (302, 403)
