"""Regresión S-LC-Feedback-V6 Bloque 0: el teléfono del contacto se guarda y
se espeja entre ClienteContacto (verdad) y los campos legacy del Cliente."""

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_editar_contacto_espeja_telefono(client, usuario_factory, cliente_factory):
    """Bug original: nombre se guardaba, teléfono no. Editar desde la ficha
    persiste TODO en ClienteContacto y lo espeja a los campos legacy."""
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    cli = cliente_factory(creado_por=admin, razon_social="KARI KARI")
    resp = client.post(
        f"/cartera/{cli.pk}/editar",
        {"razon_social": "KARI KARI", "rfc": "", "estado": "activo",
         "direccion": "", "notas": "",
         "contactos-TOTAL_FORMS": "1", "contactos-INITIAL_FORMS": "0",
         "contactos-MIN_NUM_FORMS": "0", "contactos-MAX_NUM_FORMS": "1000",
         "contactos-0-nombre": "Lazaro Moussali",
         "contactos-0-email": "lazaro@karikari.mx",
         "contactos-0-telefono": "+52 56 2746 3216",
         "contactos-0-puesto": ""},
        follow=True,
    )
    assert resp.status_code == 200
    cli.refresh_from_db()
    # (a) La verdad: ClienteContacto.
    cp = cli.contacto_principal
    assert cp is not None
    assert cp.nombre == "Lazaro Moussali"
    assert cp.telefono == "+52 56 2746 3216"
    # (b) El espejo legacy (búsqueda/listas).
    assert cli.nombre_contacto == "Lazaro Moussali"
    assert cli.telefono == "+52 56 2746 3216"
    assert cli.email_contacto == "lazaro@karikari.mx"
    # (c) El detalle lo muestra.
    body = client.get(f"/cartera/{cli.pk}/").content.decode()
    assert "Lazaro Moussali" in body
    assert "+52 56 2746 3216" in body


def test_nuevo_cliente_con_contacto_espeja(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    client.post(
        "/cartera/nuevo",
        {"razon_social": "Espejo S.A.", "rfc": "", "estado": "prospecto",
         "direccion": "", "notas": "",
         "contactos-TOTAL_FORMS": "1", "contactos-INITIAL_FORMS": "0",
         "contactos-MIN_NUM_FORMS": "0", "contactos-MAX_NUM_FORMS": "1000",
         "contactos-0-nombre": "Ana", "contactos-0-email": "",
         "contactos-0-telefono": "555 123 4567", "contactos-0-puesto": ""},
        follow=True,
    )
    from apps.la_cartera.models import Cliente
    cli = Cliente.objects.get(razon_social="Espejo S.A.")
    assert cli.telefono == "555 123 4567"
    assert cli.nombre_contacto == "Ana"


def test_cliente_inline_desde_proyecto_crea_contacto(client, usuario_factory):
    """El modal '+ Nuevo cliente' del form de Proyecto escribía SOLO los campos
    legacy; ahora también crea el ClienteContacto principal (espejo inverso)."""
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(
        "/proyectos/cliente-nuevo/",
        {"razon_social": "Inline S.A.", "rfc": "",
         "nombre_contacto": "Pedro", "email_contacto": "pedro@inline.mx",
         "telefono": "55 0000 1111"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    from apps.la_cartera.models import Cliente
    cli = Cliente.objects.get(razon_social="Inline S.A.")
    cp = cli.contacto_principal
    assert cp is not None
    assert cp.nombre == "Pedro"
    assert cp.telefono == "55 0000 1111"
    assert cp.principal is True


def test_espejo_no_pisa_legacy_sin_contactos(cliente_factory, usuario_factory):
    """Si el cliente no tiene ClienteContacto, el espejo no borra lo legacy."""
    from apps.la_cartera.services import espejar_contacto_principal
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    cli.nombre_contacto = "Legacy"
    cli.telefono = "555"
    cli.save()
    espejar_contacto_principal(cli)
    cli.refresh_from_db()
    assert cli.nombre_contacto == "Legacy"
    assert cli.telefono == "555"


def test_asegurar_contacto_no_duplica(cliente_factory, usuario_factory):
    from apps.la_cartera.models import ClienteContacto
    from apps.la_cartera.services import asegurar_contacto_principal
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    ClienteContacto.objects.create(cliente=cli, nombre="Ya existo", principal=True)
    cli.nombre_contacto = "Otro"
    cli.telefono = "999"
    asegurar_contacto_principal(cli)
    assert cli.contactos.count() == 1
