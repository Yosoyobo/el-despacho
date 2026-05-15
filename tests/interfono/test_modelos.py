import pytest

pytestmark = pytest.mark.django_db


def _crear_sub(usuario_factory, **kwargs):
    from interfono.models import InterfonoSuscripcion

    defaults = {
        "usuario": kwargs.pop("usuario", None) or usuario_factory(),
        "endpoint": kwargs.pop("endpoint", "https://fcm.googleapis.com/fcm/send/abc123"),
        "p256dh": "BNxxx",
        "auth": "AAAxxx",
        "user_agent": kwargs.pop("user_agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) Chrome/120"),
    }
    defaults.update(kwargs)
    return InterfonoSuscripcion.objects.create(**defaults)


def test_crear_suscripcion(usuario_factory):
    sub = _crear_sub(usuario_factory)
    assert sub.activa is True
    assert sub.desactivada_en is None


def test_endpoint_unico(usuario_factory):
    _crear_sub(usuario_factory)
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        _crear_sub(usuario_factory)


def test_etiqueta_dispositivo_chrome_mac(usuario_factory):
    sub = _crear_sub(usuario_factory)
    assert "Chrome" in sub.etiqueta_dispositivo()
    assert "Mac" in sub.etiqueta_dispositivo()


def test_etiqueta_dispositivo_firefox_linux(usuario_factory):
    sub = _crear_sub(usuario_factory, user_agent="Mozilla/5.0 (X11; Linux x86_64) Firefox/121")
    assert "Firefox" in sub.etiqueta_dispositivo()
    assert "Linux" in sub.etiqueta_dispositivo()


def test_etiqueta_dispositivo_ua_vacio(usuario_factory):
    sub = _crear_sub(usuario_factory, user_agent="")
    et = sub.etiqueta_dispositivo()
    assert "Navegador" in et


def test_envio_basico(usuario_factory):
    from interfono.models import InterfonoEnvio
    autor = usuario_factory(rol="super_admin")
    envio = InterfonoEnvio.objects.create(
        autor=autor, audiencia="todos", audiencia_label="Todos los usuarios activos",
        titulo="Junta", cuerpo="A las 3pm en la sala.",
    )
    assert envio.entregadas == 0
    assert envio.fallidas == 0
    assert envio.suscripciones_invalidadas == 0
    assert envio.creado_en is not None
