"""Tests de vistas de La Cartera."""

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_anonimo_no_accede_a_lista(client):
    resp = client.get("/cartera/")
    assert resp.status_code in (302, 301)
    assert "/sign-in" in resp["Location"]


def test_disenador_no_accede_a_cartera(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/cartera/")
    assert resp.status_code == 403


def test_contador_lee_pero_no_crea(client, usuario_factory):
    c = usuario_factory(rol="contador")
    client.force_login(c)
    assert client.get("/cartera/").status_code == 200
    # Contador no puede llegar al formulario.
    assert client.get("/cartera/nuevo").status_code == 403


def test_admin_crea_cliente(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(
        "/cartera/nuevo",
        {"razon_social": "ACME S.A.", "rfc": "ACM010101AAA", "estado": "activo",
         "nombre_contacto": "", "email_contacto": "", "telefono": "", "direccion": "", "notas": ""},
        follow=True,
    )
    assert resp.status_code == 200
    from apps.la_cartera.models import Cliente
    assert Cliente.objects.filter(razon_social="ACME S.A.").exists()


def test_crear_con_rfc_invalido_falla(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(
        "/cartera/nuevo",
        {"razon_social": "X", "rfc": "ABC", "estado": "prospecto",
         "nombre_contacto": "", "email_contacto": "", "telefono": "", "direccion": "", "notas": ""},
    )
    assert resp.status_code == 200  # vuelve al form con error
    from apps.la_cartera.models import Cliente
    assert not Cliente.objects.filter(razon_social="X").exists()


def test_editar_cliente(client, usuario_factory, cliente_factory):
    admin = usuario_factory(rol="dueno")
    client.force_login(admin)
    cli = cliente_factory(creado_por=admin, razon_social="Vieja S.A.")
    resp = client.post(
        f"/cartera/{cli.pk}/editar",
        {"razon_social": "Nueva S.A.", "rfc": "", "estado": "activo",
         "nombre_contacto": "", "email_contacto": "", "telefono": "", "direccion": "", "notas": ""},
        follow=True,
    )
    assert resp.status_code == 200
    cli.refresh_from_db()
    assert cli.razon_social == "Nueva S.A."


def test_archivar_es_soft_delete(client, usuario_factory, cliente_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    cli = cliente_factory(creado_por=admin)
    client.post(f"/cartera/{cli.pk}/archivar")
    cli.refresh_from_db()
    assert cli.activo is False
    from apps.la_cartera.models import Cliente
    assert cli.pk in [c.pk for c in Cliente.objects.all()]   # sigue en DB
    assert cli.pk not in [c.pk for c in Cliente.activos.all()]  # oculto del default


def test_disenador_403_a_nuevo(client, usuario_factory):
    d = usuario_factory(rol="disenador")
    client.force_login(d)
    assert client.get("/cartera/nuevo").status_code == 403
