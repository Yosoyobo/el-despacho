import pytest

pytestmark = pytest.mark.django_db


def test_resolver_todos(usuario_factory):
    usuario_factory(rol="super_admin", email="a@x.com")
    usuario_factory(rol="contador", email="b@x.com")
    inactivo = usuario_factory(rol="disenador", email="c@x.com")
    inactivo.is_active = False
    inactivo.save()

    from lib.interfono import _resolver_usuarios
    emails = sorted(u.email for u in _resolver_usuarios("todos"))
    assert emails == ["a@x.com", "b@x.com"]


def test_resolver_por_rol(usuario_factory):
    usuario_factory(rol="contador", email="cont1@x.com")
    usuario_factory(rol="contador", email="cont2@x.com")
    usuario_factory(rol="disenador", email="dis@x.com")
    from lib.interfono import _resolver_usuarios
    emails = sorted(u.email for u in _resolver_usuarios("rol:contador"))
    assert emails == ["cont1@x.com", "cont2@x.com"]


def test_resolver_usuario_individual(usuario_factory):
    u = usuario_factory(email="solo@x.com")
    from lib.interfono import _resolver_usuarios
    resultado = list(_resolver_usuarios(f"usuario:{u.pk}"))
    assert len(resultado) == 1
    assert resultado[0].email == "solo@x.com"


def test_resolver_usuario_id_invalido():
    from lib.interfono import _resolver_usuarios
    assert list(_resolver_usuarios("usuario:no-numerico")) == []


def test_resolver_audiencia_desconocida(usuario_factory):
    usuario_factory()
    from lib.interfono import _resolver_usuarios
    assert list(_resolver_usuarios("loquesea")) == []
