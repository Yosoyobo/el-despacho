"""UI de Configuración Fiscal en La Gerencia (/ajustes/fiscal/). Solo super_admin."""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def test_panel_super_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/ajustes/fiscal/")
    assert resp.status_code == 200
    assert "Figuras fiscales" in resp.content.decode()


def test_panel_disenador_sin_acceso(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/ajustes/fiscal/")
    assert resp.status_code in (302, 403)


def test_guardar_figuras(client, usuario_factory):
    from ajustes.models import ConfiguracionFiscal
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/fiscal/", {
        "regimen": "resico_pf",
        "isr_base": "ingresos",
        "isr_tasa": "2.5",
        "ptu_tasa": "10",
        "iva_tasa": "16",
        # ptu_aplica desmarcado
    })
    assert resp.status_code in (302, 200)
    cfg = ConfiguracionFiscal.obtener()
    assert cfg.regimen == "resico_pf"
    assert cfg.isr_base == "ingresos"
    assert cfg.isr_tasa == Decimal("2.500")
    assert cfg.ptu_aplica is False
    assert cfg.iva_tasa == Decimal("16.000")
