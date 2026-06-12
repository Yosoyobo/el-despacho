"""El Directorio — CRUD usuarios + permisos."""

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def test_disenador_no_accede(client, usuario_factory):
    client.force_login(usuario_factory(rol="disenador"))
    resp = client.get("/directorio/")
    assert resp.status_code == 403


def test_contador_no_accede(client, usuario_factory):
    client.force_login(usuario_factory(rol="contador"))
    resp = client.get("/directorio/")
    assert resp.status_code == 403


def test_admin_lista(client, usuario_factory):
    admin = usuario_factory(rol="super_admin", email="admin@x.com")
    usuario_factory(rol="contador", email="cont@x.com")
    client.force_login(admin)
    resp = client.get("/directorio/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "admin@x.com" in body
    assert "cont@x.com" in body


def test_admin_crea_usuario(client, usuario_factory):
    from cuentas.models.usuario import Usuario
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/directorio/nuevo", {
        "email": "nuevo@x.com",
        "nombre_completo": "Usuario Nuevo",
        "rol": "miembro",
        "password": "contraseñasegura",
        "is_active": "on",
    })
    assert resp.status_code == 302
    u = Usuario.objects.get(email="nuevo@x.com")
    assert u.rol == "miembro"
    assert u.is_active is True


def test_admin_edita_rol(client, usuario_factory):
    target = usuario_factory(rol="disenador", email="t@x.com")
    client.force_login(usuario_factory(rol="dueno"))
    resp = client.post(f"/directorio/{target.pk}/editar", {
        "email": "t@x.com",
        "nombre_completo": "Editado",
        "rol": "miembro",
        "is_active": "on",
        "password": "",
    })
    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.rol == "miembro"
    assert target.nombre_completo == "Editado"


def test_promover_a_super_admin_activa_flags(client, usuario_factory):
    target = usuario_factory(rol="contador", email="t@x.com")
    assert target.is_superuser is False
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(f"/directorio/{target.pk}/editar", {
        "email": "t@x.com", "nombre_completo": "T", "rol": "super_admin",
        "is_active": "on", "password": "",
    })
    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.rol == "super_admin"
    assert target.is_superuser is True
    assert target.is_staff is True


def test_degradar_de_super_admin_limpia_flags(client, usuario_factory):
    # Bug del checkmark: degradar dejaba is_superuser/is_staff pegados en True.
    target = usuario_factory(rol="super_admin", email="t@x.com")
    target.is_staff = True
    target.is_superuser = True
    target.save(update_fields=["is_staff", "is_superuser"])
    client.force_login(usuario_factory(rol="super_admin", email="admin@x.com"))
    resp = client.post(f"/directorio/{target.pk}/editar", {
        "email": "t@x.com", "nombre_completo": "T", "rol": "miembro",
        "is_active": "on", "password": "",
    })
    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.rol == "miembro"
    assert target.is_superuser is False
    assert target.is_staff is False


def test_admin_bloquea_a_otro(client, usuario_factory):
    target = usuario_factory(rol="contador")
    assert target.is_active is True
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(f"/directorio/{target.pk}/bloquear")
    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.is_active is False


def test_no_se_puede_bloquear_a_si_mismo(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(f"/directorio/{admin.pk}/bloquear", follow=True)
    assert resp.status_code == 200
    admin.refresh_from_db()
    assert admin.is_active is True
