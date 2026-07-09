"""Fase 6 (LC 2026-07) — taxonomía de proveedores (6 core + 19 subcategorías)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_seed_6_core_19_sub():
    from apps.el_catalogo.models import CategoriaProveedor, SubcategoriaProveedor
    assert CategoriaProveedor.objects.count() == 6
    assert SubcategoriaProveedor.objects.count() == 19
    # Las 6 core esperadas.
    slugs = set(CategoriaProveedor.objects.values_list("slug", flat=True))
    assert slugs == {"materiales", "confeccion", "impresion", "promocionales", "letreros", "servicios"}


def test_subcategoria_hereda_color_de_core():
    from apps.el_catalogo.models import CategoriaProveedor, SubcategoriaProveedor
    sub = SubcategoriaProveedor.objects.get(slug="serigrafia")
    core = CategoriaProveedor.objects.get(slug="impresion")
    assert sub.color == core.color  # heredado


def test_form_guarda_subcategorias(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor, SubcategoriaProveedor
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    subs = list(SubcategoriaProveedor.objects.filter(slug__in=["telas", "bordado"]).values_list("pk", flat=True))
    resp = client.post("/catalogo/proveedores/nuevo", {
        "razon_social": "Textiles del Norte", "activo": "on",
        "fiscal_igual": "on", "subcategorias": subs,
    })
    assert resp.status_code in (301, 302)
    prov = Proveedor.objects.get(razon_social="Textiles del Norte")
    assert set(prov.subcategorias.values_list("pk", flat=True)) == set(subs)


def test_lista_muestra_subcategoria(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor, SubcategoriaProveedor
    admin = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social="Serigrafía López", activo=True)
    prov.subcategorias.add(SubcategoriaProveedor.objects.get(slug="serigrafia"))
    client.force_login(admin)
    resp = client.get("/catalogo/proveedores/")
    assert resp.status_code == 200
    assert b"Serigraf\xc3\xada" in resp.content  # el nombre de la subcategoría aparece como pill
