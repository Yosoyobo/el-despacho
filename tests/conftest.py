"""Bootstrap de tests: garantiza BOVEDA_MASTER_KEY antes de cualquier import de lib."""

import os
import secrets
import sys

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


def _emitir_de_mentiras(evento) -> None:
    """El `emitir` de las pruebas sin Redis: no encola nada.

    Es UNA función de módulo, no una lambda por test, para poder reconocerla
    por identidad al limpiar (ver `_emitir_noop`)."""


def _es_modulo_de_pruebas(nombre: str) -> bool:
    """Los módulos de pruebas NO se tocan: uno que haga
    `from lib.portavoz import emitir` para probar la función de verdad (con su
    propio Redis falso) tiene que recibir la de verdad."""
    hoja = nombre.rsplit(".", 1)[-1]
    return nombre.startswith("tests.") or hoja.startswith("test_") or hoja == "conftest"


def _modulos_con_emitir(objetivo):
    """Los módulos cargados cuyo `emitir` ES `objetivo` (por identidad).

    Se lee el `__dict__` y no `getattr`: un módulo con `__getattr__` perezoso
    podría importar cosas o lanzar sólo por preguntarle."""
    for nombre, modulo in list(sys.modules.items()):
        if modulo is None or _es_modulo_de_pruebas(nombre):
            continue
        try:
            atributos = vars(modulo)
        except TypeError:
            continue
        if atributos.get("emitir") is objetivo:
            yield modulo


@pytest.fixture(autouse=True)
def _emitir_noop(monkeypatch, request):
    """Para tests Django, neutraliza `lib.portavoz.emitir` si Redis no responde,
    para no acoplar el resultado al estado de la cola. Tests del worker pasan
    `REDIS_OK=True` y bypassean este fixture marcándose con `redis`.

    Hasta S-Deuda-Sep28 parchaba una LISTA fija de módulos, que se quedó vieja:
    los que hacen `from lib.portavoz import emitir` y no estaban en ella (p. ej.
    `apps.cotizaciones.services`) conservaban la función de verdad y, sin Redis,
    reventaban con un `PortavozError` que no tenía nada que ver con lo probado.
    Ahora se parchea en el origen **y** en todo módulo cargado cuyo `emitir` sea
    esa misma función — por identidad, así que el módulo que ya lo había
    cambiado por su cuenta se respeta.

    Un módulo que se importa POR PRIMERA VEZ durante el test se queda con la
    función de mentiras (la toma del origen parchado). Al terminar se le
    devuelve la de verdad: si no, la llevaría para siempre y un test posterior
    marcado `redis` probaría una función que no encola nada.
    """
    if "redis" in request.keywords or REDIS_OK:
        yield
        return
    devolver = _neutralizar_emitir(monkeypatch)
    yield
    devolver()


def _neutralizar_emitir(monkeypatch):
    """Cambia `emitir` por el de mentiras en el origen y en cada módulo cargado.

    Devuelve la función que, al terminar la prueba, le regresa el `emitir` de
    verdad a los módulos que lo tomaron del origen YA parchado (los que se
    importaron a media prueba). Lo demás lo deshace el propio `monkeypatch`,
    que corre después. Aparte del fixture para poder probarlo solo.
    """
    from lib import portavoz

    original = portavoz.emitir
    parchados = set()
    monkeypatch.setattr(portavoz, "emitir", _emitir_de_mentiras)
    for modulo in _modulos_con_emitir(original):
        monkeypatch.setattr(modulo, "emitir", _emitir_de_mentiras)
        parchados.add(modulo.__name__)

    def _devolver():
        for modulo in _modulos_con_emitir(_emitir_de_mentiras):
            if modulo is not portavoz and modulo.__name__ not in parchados:
                modulo.emitir = original

    return _devolver


@pytest.fixture(autouse=True)
def _almacen_aislado():
    """El Almacén (S-Medios-V1) recuerda los `meta.json` en el proceso porque son
    inmutables. Entre tests hay que olvidarlos: dos tests que usen la misma
    llave con contenidos distintos se contaminarían."""
    from lib import almacen

    almacen.olvidar_meta()
    yield
    almacen.olvidar_meta()


@pytest.fixture(autouse=True)
def _cache_aislada():
    """El caché de Django vive en el PROCESO y el rollback de cada test no lo
    toca: un test que cachea algo derivado de filas que luego desaparecen se lo
    hereda al siguiente. Serial el orden lo escondía; con xdist los tests se
    reparten distinto y salía a la luz (`mapa_alias` del catálogo fue el caso).

    Aislarlo aquí hace la suite determinista sin importar el orden ni cuántos
    workers corran. Es barato: LocMemCache, declarado en `django_settings`."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


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
        # C6 S-LC-Feedback-V6: fecha_inicio/fecha_compromiso son DateTimeField
        # aware. Si un test pasa un `date`, lo elevamos a datetime 12:00 aware.
        import datetime as _dt

        from django.utils import timezone as _tz
        for campo in ("fecha_inicio", "fecha_compromiso"):
            val = defaults.get(campo)
            if isinstance(val, _dt.date) and not isinstance(val, _dt.datetime):
                naive = _dt.datetime.combine(val, _dt.time(12, 0))
                defaults[campo] = _tz.make_aware(naive) if _tz.is_naive(naive) else naive
        return Proyecto.objects.create(**defaults)

    return _crear
