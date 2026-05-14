from types import SimpleNamespace

from lib.permisos import (
    es_admin,
    es_super_admin,
    puede_ver_ajustes,
    puede_ver_finanzas,
)


def u(rol):
    return SimpleNamespace(rol=rol)


def test_super_admin_es_admin():
    assert es_admin(u("super_admin"))
    assert es_super_admin(u("super_admin"))


def test_dueno_es_admin_pero_no_super():
    assert es_admin(u("dueno"))
    assert not es_super_admin(u("dueno"))


def test_contador_no_es_admin():
    assert not es_admin(u("contador"))


def test_disenador_no_es_admin():
    assert not es_admin(u("disenador"))


def test_solo_super_admin_ve_ajustes():
    assert puede_ver_ajustes(u("super_admin"))
    assert not puede_ver_ajustes(u("dueno"))
    assert not puede_ver_ajustes(u("contador"))
    assert not puede_ver_ajustes(u("disenador"))


def test_finanzas_visibles():
    assert puede_ver_finanzas(u("super_admin"))
    assert puede_ver_finanzas(u("dueno"))
    assert puede_ver_finanzas(u("contador"))
    assert not puede_ver_finanzas(u("disenador"))
