"""UI de La Cobranza en La Gerencia (/ajustes/cobranza/). Solo super_admin."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def test_panel_super_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/ajustes/cobranza/")
    assert resp.status_code == 200
    assert "La Cobranza" in resp.content.decode()


def test_panel_disenador_sin_acceso(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/ajustes/cobranza/")
    assert resp.status_code in (302, 403)


def test_guardar_activa_y_cadencia(client, usuario_factory):
    from ajustes.models import ConfiguracionCobranza
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cobranza/", {
        "activa": "1",
        "dias_entre_recordatorios": "5",
        "max_recordatorios": "3",
        "recordar_pre_vencimiento_dias": "2",
    })
    assert resp.status_code in (302, 200)
    cfg = ConfiguracionCobranza.obtener()
    assert cfg.activa is True
    assert cfg.dias_entre_recordatorios == 5
    assert cfg.max_recordatorios == 3
    assert cfg.recordar_pre_vencimiento_dias == 2
