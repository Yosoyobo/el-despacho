"""Helpers de `lib.permisos` por rol del sistema.

Desde S-Deuda-Permisos los helpers leen el PERMISO que el rol trae (filas de
`PermisoUsuario` sembradas por el signal con los defaults del rol), así que
estas pruebas usan usuarios de verdad en la base y no un `SimpleNamespace`
con un atributo `rol`. Lo que afirman es lo mismo que antes.
"""

import pytest

from lib.permisos import (
    es_super_admin,
    puede_gestionar_proyectos,
    puede_ver_ajustes,
    puede_ver_finanzas,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def u(usuario_factory):
    return lambda rol: usuario_factory(rol=rol)


def test_super_admin_gestiona_proyectos(u):
    sa = u("super_admin")
    assert puede_gestionar_proyectos(sa)
    assert es_super_admin(sa)


def test_dueno_gestiona_proyectos_pero_no_es_super(u):
    d = u("dueno")
    assert puede_gestionar_proyectos(d)
    assert not es_super_admin(d)


def test_contador_no_gestiona_proyectos(u):
    assert not puede_gestionar_proyectos(u("contador"))


def test_disenador_no_gestiona_proyectos(u):
    assert not puede_gestionar_proyectos(u("disenador"))


def test_solo_super_admin_ve_ajustes(u):
    assert puede_ver_ajustes(u("super_admin"))
    assert not puede_ver_ajustes(u("dueno"))
    assert not puede_ver_ajustes(u("contador"))
    assert not puede_ver_ajustes(u("disenador"))


def test_finanzas_visibles(u):
    assert puede_ver_finanzas(u("super_admin"))
    assert puede_ver_finanzas(u("dueno"))
    assert puede_ver_finanzas(u("contador"))
    assert not puede_ver_finanzas(u("disenador"))
