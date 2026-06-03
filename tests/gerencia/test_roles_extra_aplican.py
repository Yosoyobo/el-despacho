"""Fix: los roles extra deben APLICAR a los checks gruesos por nombre de rol
(es_admin, puede_ver_finanzas, requires_role), no solo al camino granular
puede(). Regresión del reporte de LC "los roles no se aplican".
"""

import pytest

from lib.permisos import (
    es_admin,
    es_super_admin,
    puede_ver_cartera,
    puede_ver_finanzas,
    roles_efectivos,
)

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def _rol(nombre):
    from cuentas.models.rol import Rol

    return Rol.objects.get(nombre=nombre)


def test_roles_efectivos_une_primario_y_extra(usuario_factory):
    u = usuario_factory(rol="disenador")
    u.roles_extra.add(_rol("contador"))
    assert roles_efectivos(u) == {"disenador", "contador"}


def test_disenador_con_rol_extra_contador_ve_finanzas(usuario_factory):
    u = usuario_factory(rol="disenador")
    assert puede_ver_finanzas(u) is False
    assert puede_ver_cartera(u) is False
    u.roles_extra.add(_rol("contador"))
    assert puede_ver_finanzas(u) is True
    assert puede_ver_cartera(u) is True


def test_disenador_con_rol_extra_dueno_es_admin(usuario_factory):
    u = usuario_factory(rol="disenador")
    assert es_admin(u) is False
    u.roles_extra.add(_rol("dueno"))
    assert es_admin(u) is True


def test_rol_extra_super_admin_escala(usuario_factory):
    u = usuario_factory(rol="contador")
    assert es_super_admin(u) is False
    u.roles_extra.add(_rol("super_admin"))
    assert es_super_admin(u) is True


def test_requires_role_honra_rol_extra(client, usuario_factory):
    """El Directorio exige super_admin/dueno; un diseñador con rol extra
    'dueno' ahora SÍ entra (antes daba 403)."""
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert client.get("/directorio/").status_code == 403
    u.roles_extra.add(_rol("dueno"))
    assert client.get("/directorio/").status_code == 200


def test_anonimo_y_sin_extra_no_rompe(usuario_factory):
    u = usuario_factory(rol="disenador")
    assert roles_efectivos(u) == {"disenador"}
    assert es_admin(u) is False
