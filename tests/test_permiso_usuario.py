"""Tests de PermisoUsuario — Pre-S2b.1."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def test_signal_seedea_al_crear_usuario(usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    u = usuario_factory(rol="dueno")
    permisos = PermisoUsuario.objects.filter(usuario=u, activo=True)
    assert permisos.count() > 0
    modulos = set(permisos.values_list("modulo", flat=True))
    assert "cartera" in modulos
    assert "proyectos" in modulos


def test_disenador_sin_cartera(usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    d = usuario_factory(rol="disenador")
    cartera = PermisoUsuario.objects.filter(usuario=d, modulo="cartera")
    assert cartera.count() == 0


def test_puede_helper(usuario_factory):
    from lib.permisos import puede
    a = usuario_factory(rol="super_admin")
    assert puede(a, "cartera", "ver")
    assert puede(a, "tesoreria", "exportar")
    assert not puede(a, "modulo_inexistente", "x")


def test_puede_usuario_inactivo(usuario_factory):
    from lib.permisos import puede
    u = usuario_factory(rol="super_admin")
    u.is_active = False
    u.save()
    assert not puede(u, "cartera", "ver")


def test_puede_anonimo():
    from lib.permisos import puede
    class _Anon:
        is_authenticated = False
    assert not puede(_Anon(), "cartera", "ver")


def test_signal_idempotente(usuario_factory):
    """Re-disparar signal no duplica filas."""
    from cuentas.models.permiso_usuario import PermisoUsuario
    from cuentas.signals import auto_seedear_permisos
    u = usuario_factory(rol="dueno")
    n0 = PermisoUsuario.objects.filter(usuario=u).count()
    auto_seedear_permisos(sender=type(u), instance=u, created=True)
    n1 = PermisoUsuario.objects.filter(usuario=u).count()
    assert n0 == n1


def test_defaults_compilados_validos():
    """Validar que cada rol tiene defaults razonables."""
    from lib.permisos_defaults import DEFAULTS_POR_ROL
    for rol in ("super_admin", "dueno", "contador", "disenador"):
        assert rol in DEFAULTS_POR_ROL
    # super_admin debería tener absolutamente todo
    assert "ver" in DEFAULTS_POR_ROL["super_admin"]["cartera"]
    assert "exportar" in DEFAULTS_POR_ROL["super_admin"]["tesoreria"]
    # diseñador NO ve tesoreria
    assert "tesoreria" not in DEFAULTS_POR_ROL["disenador"]


def test_contador_ve_tesoreria(usuario_factory):
    from lib.permisos import puede
    c = usuario_factory(rol="contador")
    assert puede(c, "tesoreria", "exportar")
    assert puede(c, "tesoreria", "capturar_ingreso")


@pytest.fixture
def _urls_gerencia(settings):
    settings.ROOT_URLCONF = "tests.urls_gerencia"


def test_ui_permisos_solo_super_admin(client, usuario_factory, _urls_gerencia):
    d = usuario_factory(rol="dueno")
    target = usuario_factory(rol="disenador")
    client.force_login(d)
    r = client.get(f"/directorio/{target.pk}/permisos")
    assert r.status_code == 403


def test_ui_permisos_super_admin_ve(client, usuario_factory, _urls_gerencia):
    a = usuario_factory(rol="super_admin")
    target = usuario_factory(rol="disenador")
    client.force_login(a)
    r = client.get(f"/directorio/{target.pk}/permisos")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Permisos" in body
    assert "proyectos" in body


def test_ui_permisos_toggle(client, usuario_factory, _urls_gerencia):
    from cuentas.models.permiso_usuario import PermisoUsuario
    a = usuario_factory(rol="super_admin")
    target = usuario_factory(rol="disenador")
    client.force_login(a)
    # Sin checkbox marcado → todos los permisos del rol quedan inactivos.
    r = client.post(f"/directorio/{target.pk}/permisos", {"permisos": []})
    assert r.status_code == 302
    activos = PermisoUsuario.objects.filter(usuario=target, activo=True).count()
    assert activos == 0


def test_ui_permisos_restablece(client, usuario_factory, _urls_gerencia):
    from cuentas.models.permiso_usuario import PermisoUsuario
    a = usuario_factory(rol="super_admin")
    target = usuario_factory(rol="disenador")
    # Desactiva todo
    PermisoUsuario.objects.filter(usuario=target).update(activo=False)
    client.force_login(a)
    r = client.post(f"/directorio/{target.pk}/permisos", {"restablecer": "1"})
    assert r.status_code == 302
    activos = PermisoUsuario.objects.filter(usuario=target, activo=True).count()
    assert activos > 0
