"""S-LC-Feedback-V2: CRUD de Unidades + quick-create de Servicio inline."""

from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_unidades_seed_idempotente():
    """La migración 0003 siembra Piezas y Metros."""
    from apps.el_catalogo.models import Unidad
    nombres = set(Unidad.objects.values_list("nombre", flat=True))
    assert "Piezas" in nombres
    assert "Metros" in nombres


def test_lista_unidades_solo_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/catalogo/unidades/")
    assert resp.status_code == 200
    assert "Piezas" in resp.content.decode()


def test_crear_unidad(client, usuario_factory):
    from apps.el_catalogo.models import Unidad
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/catalogo/unidades/nueva", {
        "nombre": "Litros", "abreviacion": "L", "orden": "30", "activa": "on",
    })
    assert resp.status_code == 302
    assert Unidad.objects.filter(nombre="Litros").exists()


def test_archivar_unidad(client, usuario_factory):
    from apps.el_catalogo.models import Unidad
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    uni = Unidad.objects.create(nombre="TestX", abreviacion="x", orden=99, activa=True)
    resp = client.post(f"/catalogo/unidades/{uni.pk}/archivar")
    assert resp.status_code == 302
    uni.refresh_from_db()
    assert uni.activa is False


def test_quick_create_servicio_devuelve_json(client, usuario_factory):
    """POST a /catalogo/quick-create/ crea Servicio y devuelve JSON con id+label."""
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    u = usuario_factory(rol="super_admin")
    cat = CategoriaServicio.objects.filter(activa=True).first()
    assert cat is not None
    client.force_login(u)
    resp = client.post("/catalogo/quick-create/", {
        "nombre": "Playera bordada inline",
        "categoria_id": cat.pk,
        "precio_base": "150.00",
    })
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data["ok"] is True
    assert data["nombre"] == "Playera bordada inline"
    assert "label" in data
    assert Servicio.objects.filter(pk=data["id"]).exists()


def test_quick_create_falta_campos_400(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/catalogo/quick-create/", {"nombre": "X"})
    assert resp.status_code == 400
