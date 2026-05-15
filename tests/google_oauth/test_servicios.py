"""Pruebas de register_or_link_google_user."""

import pytest

pytestmark = pytest.mark.django_db


def _perfil(sub="g-1", email="oscar@bautista.mx", foto="https://x/foto.jpg"):
    from lib.google_oauth import PerfilGoogle
    return PerfilGoogle(
        sub=sub, email=email, email_verified=True,
        nombre="Oscar", apellido="Bautista", foto_url=foto, locale="es-MX",
    )


def test_vincula_primer_login(usuario_factory):
    u = usuario_factory(rol="super_admin", email="oscar@bautista.mx")
    from auth_google.servicios import register_or_link_google_user
    out = register_or_link_google_user(_perfil())
    assert out.pk == u.pk
    out.refresh_from_db()
    assert out.google_sub == "g-1"
    assert out.google_email == "oscar@bautista.mx"
    assert out.google_vinculado_en is not None
    assert out.avatar_url == "https://x/foto.jpg"


def test_segunda_vez_no_reescribe(usuario_factory):
    u = usuario_factory(rol="super_admin", email="oscar@bautista.mx")
    u.google_sub = "g-1"
    u.google_email = "oscar@bautista.mx"
    from django.utils import timezone
    u.google_vinculado_en = timezone.now()
    u.avatar_url = "https://x/old.jpg"
    u.save()

    from auth_google.servicios import register_or_link_google_user
    out = register_or_link_google_user(_perfil(foto="https://x/nueva.jpg"))
    assert out.pk == u.pk
    out.refresh_from_db()
    assert out.avatar_url == "https://x/old.jpg"  # no sobrescribe avatar existente


def test_email_no_registrado_levanta(usuario_factory):
    usuario_factory(email="otro@x.com")
    from auth_google.servicios import register_or_link_google_user
    from lib.google_oauth import GoogleOAuthCuentaNoRegistrada
    with pytest.raises(GoogleOAuthCuentaNoRegistrada) as ei:
        register_or_link_google_user(_perfil(email="desconocido@x.com"))
    assert ei.value.email == "desconocido@x.com"


def test_usuario_inactivo_levanta(usuario_factory):
    u = usuario_factory(rol="contador", email="inactivo@x.com")
    u.is_active = False
    u.save()
    from auth_google.servicios import register_or_link_google_user
    from lib.google_oauth import GoogleOAuthCuentaNoRegistrada
    with pytest.raises(GoogleOAuthCuentaNoRegistrada):
        register_or_link_google_user(_perfil(email="inactivo@x.com"))


def test_google_sub_ya_asignado_a_otra_cuenta(usuario_factory):
    u = usuario_factory(rol="dueno", email="oscar@bautista.mx")
    u.google_sub = "g-original"
    u.save()
    from auth_google.servicios import register_or_link_google_user
    from lib.google_oauth import GoogleOAuthYaVinculadoAOtra
    with pytest.raises(GoogleOAuthYaVinculadoAOtra):
        register_or_link_google_user(_perfil(sub="g-distinto"))


def test_lookup_por_google_sub_es_case_insensitive_en_email(usuario_factory):
    """Si el usuario ya está vinculado, lookup por sub funciona aunque el email
    en Google venga con casing distinto."""
    u = usuario_factory(email="oscar@bautista.mx")
    u.google_sub = "g-1"
    u.save()
    from auth_google.servicios import register_or_link_google_user
    out = register_or_link_google_user(_perfil(email="OSCAR@BAUTISTA.MX"))
    assert out.pk == u.pk
