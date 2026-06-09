"""S-LC-Buzon-V2: CRUD de Tipos del Buzón en Gerencia."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def test_lista_super_admin(client, usuario_factory):
    from buzon.models import TipoBuzon
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/catalogos/tipos-buzon/")
    assert resp.status_code == 200
    assert b"Sugerencia" in resp.content
    assert TipoBuzon.objects.filter(sistema=True).count() >= 3


def test_dueno_sin_acceso(client, usuario_factory):
    dueno = usuario_factory(rol="dueno")
    client.force_login(dueno)
    resp = client.get("/catalogos/tipos-buzon/")
    assert resp.status_code == 403


def test_crear_tipo_custom(client, usuario_factory):
    from buzon.models import TipoBuzon
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/tipos-buzon/nuevo/", data={
        "label": "Felicitación", "color": "#12b76a", "orden": 40, "activo": "on",
    })
    assert resp.status_code in (301, 302)
    obj = TipoBuzon.objects.get(label="Felicitación")
    assert obj.sistema is False
    assert obj.slug and obj.color == "#12b76a"


def test_no_borra_tipo_sistema(client, usuario_factory):
    from buzon.models import TipoBuzon
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    client.post("/catalogos/tipos-buzon/sugerencia/borrar/")
    assert TipoBuzon.objects.filter(slug="sugerencia").exists()


def test_toggle_oculta_tipo(client, usuario_factory):
    from buzon.models import TipoBuzon
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    client.post("/catalogos/tipos-buzon/otro/toggle/")
    assert TipoBuzon.objects.get(slug="otro").activo is False
