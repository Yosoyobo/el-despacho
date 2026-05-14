"""Bootstrap de tests: garantiza BOVEDA_MASTER_KEY antes de cualquier import de lib."""

import os
import secrets

import pytest

os.environ.setdefault("BOVEDA_MASTER_KEY", secrets.token_hex(32))
os.environ.setdefault("DJANGO_SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.django_settings")


def _redis_disponible() -> bool:
    try:
        import redis as _r

        cli = _r.Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=0.3)
        return bool(cli.ping())
    except Exception:
        return False


REDIS_OK = _redis_disponible()


def pytest_collection_modifyitems(config, items):
    skip_redis = pytest.mark.skip(reason="Redis no disponible en REDIS_URL")
    for item in items:
        if "redis" in item.keywords and not REDIS_OK:
            item.add_marker(skip_redis)


@pytest.fixture(autouse=True)
def _emitir_noop(monkeypatch, request):
    """Para tests Django, neutraliza lib.portavoz.emitir si Redis no responde,
    para no acoplar el resultado al estado de la cola. Tests del worker
    pasan REDIS_OK=True y bypassean este fixture marcándose con `redis`."""
    if "redis" in request.keywords:
        return
    if REDIS_OK:
        return
    from lib import portavoz

    noop = lambda evt: None  # noqa: E731
    monkeypatch.setattr(portavoz, "emitir", noop)
    # Las vistas importan `emitir` directamente — parchear cada módulo.
    for nombre in (
        "apps.la_cartera.views",
        "apps.los_proyectos.views",
        "apps.el_pizarron.views",
        "apps.el_directorio.views",
        "apps.los_ajustes.views",
    ):
        try:
            mod = __import__(nombre, fromlist=["emitir"])
            if hasattr(mod, "emitir"):
                monkeypatch.setattr(mod, "emitir", noop)
        except ImportError:
            pass


@pytest.fixture
def usuario_factory(db):
    """Crea Usuarios de prueba con rol arbitrario."""
    from cuentas.models.usuario import Usuario

    contador = {"n": 0}

    def _crear(rol="disenador", email=None, password="contraseña-de-prueba"):
        contador["n"] += 1
        email = email or f"u{contador['n']}@ejemplo.com"
        u = Usuario(email=email, nombre_completo=f"Usuario {contador['n']}", rol=rol)
        u.set_password(password)
        u.is_active = True
        u.save()
        return u

    return _crear


@pytest.fixture
def cliente_factory(db, usuario_factory):
    from apps.la_cartera.models import Cliente

    contador = {"n": 0}

    def _crear(creado_por=None, **kwargs):
        contador["n"] += 1
        defaults = {
            "razon_social": kwargs.pop("razon_social", f"Cliente {contador['n']} S.A."),
            "estado": kwargs.pop("estado", "activo"),
            "rfc": kwargs.pop("rfc", ""),
        }
        defaults.update(kwargs)
        defaults["creado_por"] = creado_por or usuario_factory(rol="super_admin")
        return Cliente.objects.create(**defaults)

    return _crear


@pytest.fixture
def proyecto_factory(db, cliente_factory, usuario_factory):
    from apps.los_proyectos.models import Proyecto

    def _crear(cliente=None, creado_por=None, **kwargs):
        cliente = cliente or cliente_factory()
        creado_por = creado_por or usuario_factory(rol="super_admin")
        defaults = {"nombre": kwargs.pop("nombre", "Proyecto de prueba"), "cliente": cliente, "creado_por": creado_por}
        defaults.update(kwargs)
        return Proyecto.objects.create(**defaults)

    return _crear
