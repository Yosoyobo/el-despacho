"""S-LC-Buzon-V2 (C5d): toggle del Buzón en Gerencia."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def test_toggle_empleado_responde(client, usuario_factory):
    from buzon.models import ConfiguracionBuzon
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    # Activar.
    client.post("/catalogos/estados-buzon/config", data={"empleado_puede_responder": "on"})
    assert ConfiguracionBuzon.obtener().empleado_puede_responder is True
    # Desactivar (checkbox ausente).
    client.post("/catalogos/estados-buzon/config", data={})
    assert ConfiguracionBuzon.obtener().empleado_puede_responder is False


def test_toggle_solo_super_admin(client, usuario_factory):
    dueno = usuario_factory(rol="dueno")
    client.force_login(dueno)
    resp = client.post("/catalogos/estados-buzon/config", data={"empleado_puede_responder": "on"})
    assert resp.status_code == 403
