"""getAuth — devuelve ContextoUsuario o None según request.user."""

from types import SimpleNamespace

from lib.sesion import ContextoUsuario, getAuth


def _req(user):
    return SimpleNamespace(user=user)


def test_sin_user_devuelve_none():
    assert getAuth(_req(None)) is None


def test_user_no_autenticado_devuelve_none():
    anon = SimpleNamespace(is_authenticated=False)
    assert getAuth(_req(anon)) is None


def test_user_autenticado_devuelve_contexto():
    user = SimpleNamespace(
        is_authenticated=True,
        pk=42,
        email="OScAr@Ejemplo.com",
        nombre_completo="Óscar B.",
        rol="dueno",
        is_active=True,
    )
    ctx = getAuth(_req(user))
    assert isinstance(ctx, ContextoUsuario)
    assert ctx.id == 42
    assert ctx.rol == "dueno"
    assert ctx.es_admin is True
    assert ctx.es_super_admin is False


def test_super_admin_flag():
    user = SimpleNamespace(
        is_authenticated=True, pk=1, email="x@y.com",
        nombre_completo="X", rol="super_admin", is_active=True,
    )
    ctx = getAuth(_req(user))
    assert ctx.es_super_admin is True
    assert ctx.es_admin is True


def test_disenador_no_es_admin():
    user = SimpleNamespace(
        is_authenticated=True, pk=2, email="d@y.com",
        nombre_completo="D", rol="disenador", is_active=True,
    )
    ctx = getAuth(_req(user))
    assert ctx.es_admin is False
    assert ctx.es_super_admin is False
