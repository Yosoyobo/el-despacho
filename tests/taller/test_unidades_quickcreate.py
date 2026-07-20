"""Quick-create de Servicio inline.

Sprint Fiscal 2026-07 (#12): el CRUD de Unidades se retiró (unidad consolidada
a 'pz'). El modelo `Unidad` y su seed se conservan por back-compat; el
quick-create ahora fuerza 'pz'.
"""

from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_quick_create_servicio_devuelve_json(client, usuario_factory):
    """POST a /catalogo/quick-create/ crea Servicio (unidad 'pz') y devuelve JSON."""
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
    srv = Servicio.objects.get(pk=data["id"])
    assert srv.unidad == "pz"  # #12: unidad consolidada.


def test_unidades_maintenance_retirado(client, usuario_factory):
    """Las rutas de mantenimiento de Unidades se retiraron (#12)."""
    from django.urls import NoReverseMatch, reverse
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    assert client.get("/catalogo/unidades/").status_code == 404
    with pytest.raises(NoReverseMatch):
        reverse("catalogo-unidades")


def test_quick_create_falta_campos_400(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/catalogo/quick-create/", {"nombre": "X"})
    assert resp.status_code == 400
