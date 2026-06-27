"""CRUD de Estados de Cotización en Gerencia (recuadro del proyecto)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def test_lista_super_admin(client, usuario_factory):
    from apps.cotizaciones.models import EstadoCotizacion
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/catalogos/estados-cotizacion/")
    assert resp.status_code == 200
    assert b"Generada" in resp.content
    assert EstadoCotizacion.objects.filter(sistema=True).count() >= 4


def test_disenador_sin_acceso(client, usuario_factory):
    disenador = usuario_factory(rol="disenador")
    client.force_login(disenador)
    resp = client.get("/catalogos/estados-cotizacion/")
    assert resp.status_code == 403


def test_crear_estado_custom(client, usuario_factory):
    from apps.cotizaciones.models import EstadoCotizacion
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-cotizacion/nuevo/", data={
        "label": "Revisión del cliente",
        "color": "#f79009",
        "orden": 15,
        "terminal": "",
        "activo": "on",
    })
    assert resp.status_code in (301, 302)
    obj = EstadoCotizacion.objects.get(label="Revisión del cliente")
    assert obj.sistema is False
    assert obj.slug
    assert obj.color == "#f79009"


def test_no_borra_estado_sistema(client, usuario_factory):
    from apps.cotizaciones.models import EstadoCotizacion
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-cotizacion/generada/borrar/")
    assert resp.status_code in (301, 302)
    assert EstadoCotizacion.objects.filter(slug="generada").exists()
