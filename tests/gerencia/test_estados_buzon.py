"""S-Buzon-Estados-V1: CRUD de Estados del Buzón en Gerencia."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def _ticket(autor, estado="nuevo"):
    from buzon.models import MensajeBuzon
    return MensajeBuzon.objects.create(
        autor=autor, tipo="otro", asunto="Asunto de prueba",
        cuerpo="Cuerpo suficientemente largo.", estado=estado,
    )


def test_lista_super_admin(client, usuario_factory):
    from buzon.models import EstadoBuzon
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/catalogos/estados-buzon/")
    assert resp.status_code == 200
    assert b"Nuevo" in resp.content
    assert EstadoBuzon.objects.filter(sistema=True).count() >= 4


def test_dueno_sin_acceso(client, usuario_factory):
    dueno = usuario_factory(rol="dueno")
    client.force_login(dueno)
    resp = client.get("/catalogos/estados-buzon/")
    assert resp.status_code == 403


def test_crear_estado_custom(client, usuario_factory):
    from buzon.models import EstadoBuzon
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-buzon/nuevo/", data={
        "label": "En seguimiento",
        "color": "#7a5af8",
        "orden": 25,
        "terminal": "",
        "activo": "on",
    })
    assert resp.status_code in (301, 302)
    obj = EstadoBuzon.objects.get(label="En seguimiento")
    assert obj.sistema is False
    assert obj.slug
    assert obj.color == "#7a5af8"


def test_color_hex_invalido_rechazado(client, usuario_factory):
    from buzon.models import EstadoBuzon
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-buzon/nuevo/", data={
        "label": "Color malo",
        "color": "badge-brand",
        "orden": 26,
        "terminal": "",
        "activo": "on",
    })
    assert resp.status_code == 200
    assert not EstadoBuzon.objects.filter(label="Color malo").exists()


def test_editar_renombra_estado_sistema(client, usuario_factory):
    from buzon.models import EstadoBuzon
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-buzon/nuevo/editar/", data={
        "label": "Sin leer",
        "color": "#0ba5ec",
        "orden": 10,
        "terminal": "",
        "activo": "on",
    })
    assert resp.status_code in (301, 302)
    obj = EstadoBuzon.objects.get(slug="nuevo")
    assert obj.label == "Sin leer"
    assert obj.sistema is True


def test_no_borra_estado_sistema(client, usuario_factory):
    from buzon.models import EstadoBuzon
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-buzon/archivado/borrar/")
    assert resp.status_code in (301, 302)
    assert EstadoBuzon.objects.filter(slug="archivado").exists()


def test_no_borra_si_tickets_lo_usan(client, usuario_factory):
    from buzon.models import EstadoBuzon
    EstadoBuzon.objects.create(
        slug="seguimiento_x", label="Seguimiento", color="#465fff",
        orden=99, terminal=False, activo=True, sistema=False,
    )
    admin = usuario_factory(rol="super_admin")
    _ticket(admin, estado="seguimiento_x")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-buzon/seguimiento_x/borrar/")
    assert resp.status_code in (301, 302)
    assert EstadoBuzon.objects.filter(slug="seguimiento_x").exists()


def test_borra_custom_sin_uso(client, usuario_factory):
    from buzon.models import EstadoBuzon
    EstadoBuzon.objects.create(
        slug="huerfano_x", label="Huérfano", color="#667085",
        orden=99, terminal=False, activo=True, sistema=False,
    )
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-buzon/huerfano_x/borrar/")
    assert resp.status_code in (301, 302)
    assert not EstadoBuzon.objects.filter(slug="huerfano_x").exists()
