"""D4 (LC 2026-07) — picker de ubicación acotado a direcciones guardadas."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_acotado_devuelve_direcciones_guardadas_sin_nominatim(client, cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cli.direccion_fiscal = "Av. Reforma 100, Cuauhtémoc, CDMX"
    cli.save()
    client.force_login(autor)
    resp = client.get("/geo/buscar?q=Reforma&acotado=1")
    assert resp.status_code == 200
    data = resp.json()
    labels = [p["label"] for p in data["pois"]]
    assert cli.razon_social in labels
    # En modo acotado SIN mapa, NO se llama a Nominatim (resultados vacíos).
    assert data["resultados"] == []


def test_acotado_por_proveedor(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor
    autor = usuario_factory(rol="super_admin")
    Proveedor.objects.create(razon_social="Serigrafías del Bajío", activo=True,
                             direccion_fiscal="Calle Sol 5, León")
    client.force_login(autor)
    resp = client.get("/geo/buscar?q=Bajío&acotado=1")
    data = resp.json()
    labels = [p["label"] for p in data["pois"]]
    assert "Serigrafías del Bajío" in labels
