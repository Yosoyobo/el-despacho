"""S-LC-Feedback-V10 — las áreas administrativas se delegan por permiso
granular (decisión Oscar: "todo, TODO, debe tener permisos granulares").

Verifica que:
  • un usuario sin el permiso de área recibe 403,
  • concederle el permiso (PermisoUsuario activo) le abre el acceso,
  • el super_admin entra siempre (failsafe duro).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def _conceder(usuario, modulo, accion):
    from cuentas.models.permiso_usuario import PermisoUsuario
    PermisoUsuario.objects.update_or_create(
        usuario=usuario, modulo=modulo, permiso=accion, defaults={"activo": True},
    )


def test_contador_sin_permiso_ajustes_403(client, usuario_factory):
    client.force_login(usuario_factory(rol="contador"))
    assert client.get("/ajustes/").status_code == 403


def test_contador_con_permiso_ajustes_entra(client, usuario_factory):
    u = usuario_factory(rol="contador")
    _conceder(u, "ajustes", "acceder")
    client.force_login(u)
    assert client.get("/ajustes/").status_code == 200


def test_super_admin_entra_a_ajustes_failsafe(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    assert client.get("/ajustes/").status_code == 200


def test_directorio_delegable_a_contador(client, usuario_factory):
    u = usuario_factory(rol="contador")
    assert client.get("/directorio/").status_code in (302, 403)  # sin sesión / sin permiso
    _conceder(u, "directorio", "ver")
    client.force_login(u)
    assert client.get("/directorio/").status_code == 200


def test_panel_avanzado_no_se_concede_con_gestionar(client, usuario_factory):
    """`directorio.gestionar` NO abre el panel avanzado (panel es su propia acción)."""
    u = usuario_factory(rol="contador")
    otro = usuario_factory(rol="disenador")
    _conceder(u, "directorio", "gestionar")
    client.force_login(u)
    assert client.get(f"/directorio/{otro.pk}/panel").status_code == 403
    _conceder(u, "directorio", "panel")
    assert client.get(f"/directorio/{otro.pk}/panel").status_code == 200
