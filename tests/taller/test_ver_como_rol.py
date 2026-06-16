"""S-Roles-V2: toggle "ver como rol" del super_admin (debug/QA).

Simula un ROL (no un usuario): mientras está activo, los permisos se evalúan
como si el super_admin solo tuviera ese rol. La salida nunca se gatea.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _rol(nombre, permisos):
    from cuentas.models.rol import Rol
    return Rol.objects.create(nombre=nombre, permisos=permisos, sistema=False)


def test_puede_honra_rol_simulado(usuario_factory):
    from lib.permisos import puede, roles_efectivos, tiene_rol
    _rol("QA", {"cartera": ["ver"]})
    sa = usuario_factory(rol="super_admin", email="sa@lc.mx")
    # Sin simular: super_admin failsafe + permisos reales.
    assert tiene_rol(sa, "super_admin")
    # Simulando el rol QA: solo ve lo que QA permite.
    sa._rol_simulado = "QA"
    assert roles_efectivos(sa) == {"QA"}
    assert not tiene_rol(sa, "super_admin")  # failsafe apagado durante la simulación
    assert puede(sa, "cartera", "ver") is True
    assert puede(sa, "tesoreria", "ver") is False


def test_superadmin_ver_como_rol_y_sale(client, usuario_factory):
    _rol("QA", {"cartera": ["ver"]})
    sa = usuario_factory(rol="super_admin", email="sa@lc.mx")
    client.force_login(sa)
    r = client.post("/ver-como-rol", {"rol": "QA"}, follow=True)
    assert r.status_code == 200
    assert client.session.get("ver_como_rol") == "QA"
    body = client.get("/").content.decode()
    assert "Viendo el sistema como el rol" in body
    client.post("/ver-como-rol/salir", follow=True)
    assert client.session.get("ver_como_rol") is None


def test_ver_como_rol_rechaza_super_admin_y_rol_inexistente(client, usuario_factory):
    sa = usuario_factory(rol="super_admin", email="sa@lc.mx")
    client.force_login(sa)
    client.post("/ver-como-rol", {"rol": "super_admin"}, follow=True)
    assert client.session.get("ver_como_rol") is None
    client.post("/ver-como-rol", {"rol": "noexiste"}, follow=True)
    assert client.session.get("ver_como_rol") is None


def test_no_superadmin_no_ver_como_rol(client, usuario_factory):
    _rol("QA", {"cartera": ["ver"]})
    u = usuario_factory(rol="disenador", email="d@lc.mx")
    client.force_login(u)
    client.post("/ver-como-rol", {"rol": "QA"}, follow=True)
    assert client.session.get("ver_como_rol") is None
