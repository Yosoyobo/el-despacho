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


def test_admin_lista_categorias_core(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/catalogo/categorias-proveedor/")
    assert resp.status_code == 200
    assert b"Materiales" in resp.content and b"Impresi" in resp.content


def test_admin_editar_color_hereda_a_subcategorias(client, usuario_factory):
    from apps.el_catalogo.models import CategoriaProveedor, SubcategoriaProveedor
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    cat = CategoriaProveedor.objects.get(slug="impresion")
    resp = client.post(f"/catalogo/categorias-proveedor/{cat.pk}/editar", {
        "nombre": cat.nombre, "color": "#123456", "orden": cat.orden, "activa": "on",
    })
    assert resp.status_code in (301, 302)
    cat.refresh_from_db()
    assert cat.color == "#123456"
    # La subcategoría hereda el nuevo color.
    sub = SubcategoriaProveedor.objects.get(slug="serigrafia")
    assert sub.color == "#123456"


# ── LC #164: el 2º filtro migra de productos (M2M vieja) a subcategorías ──────

def test_filtro_por_subcategoria(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor, SubcategoriaProveedor
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    serig = SubcategoriaProveedor.objects.get(slug="serigrafia")
    telas = SubcategoriaProveedor.objects.get(slug="telas")
    p_serig = Proveedor.objects.create(razon_social="Impresos ACME", activo=True)
    p_serig.subcategorias.add(serig)
    p_telas = Proveedor.objects.create(razon_social="Telas SA", activo=True)
    p_telas.subcategorias.add(telas)
    resp = client.get(f"/catalogo/proveedores/?subcategoria={serig.pk}")
    assert resp.status_code == 200
    assert b"Impresos ACME" in resp.content
    assert b"Telas SA" not in resp.content


def test_filtro_por_categoria_core(client, usuario_factory):
    from apps.el_catalogo.models import CategoriaProveedor, Proveedor, SubcategoriaProveedor
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    impresion = CategoriaProveedor.objects.get(slug="impresion")
    serig = SubcategoriaProveedor.objects.get(slug="serigrafia")
    telas = SubcategoriaProveedor.objects.get(slug="telas")
    p1 = Proveedor.objects.create(razon_social="Solo Impresion", activo=True)
    p1.subcategorias.add(serig)
    p2 = Proveedor.objects.create(razon_social="Solo Telas", activo=True)
    p2.subcategorias.add(telas)
    resp = client.get(f"/catalogo/proveedores/?categoria={impresion.pk}")
    assert resp.status_code == 200
    assert b"Solo Impresion" in resp.content
    assert b"Solo Telas" not in resp.content


def test_chips_2do_nivel_son_subcategorias(client, usuario_factory):
    """LC #164: el segundo filtro muestra SUBcategorías, no productos del catálogo."""
    from apps.el_catalogo.models import CategoriaProveedor
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    impresion = CategoriaProveedor.objects.get(slug="impresion")
    resp = client.get(f"/catalogo/proveedores/?categoria={impresion.pk}")
    assert resp.status_code == 200
    assert b"Serigraf\xc3\xada" in resp.content        # subcategoría de Impresión → chip
    assert b"Subcategor\xc3\xadas" in resp.content     # encabezado del 2º filtro


def test_crud_subcategoria_crear_y_editar(client, usuario_factory):
    from apps.el_catalogo.models import CategoriaProveedor, SubcategoriaProveedor
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    core = CategoriaProveedor.objects.get(slug="materiales")
    # Crear (slug autogenerado)
    resp = client.post("/catalogo/categorias-proveedor/subcategorias/nueva", {
        "categoria": core.pk, "nombre": "Vinil adhesivo", "orden": 50, "activa": "on",
    })
    assert resp.status_code in (301, 302)
    sub = SubcategoriaProveedor.objects.get(nombre="Vinil adhesivo")
    assert sub.slug and sub.categoria_id == core.pk
    # Editar: cambia orden y desactiva (sin enviar 'activa')
    resp = client.post(f"/catalogo/categorias-proveedor/subcategorias/{sub.pk}/editar", {
        "categoria": core.pk, "nombre": "Vinil adhesivo", "orden": 60,
    })
    assert resp.status_code in (301, 302)
    sub.refresh_from_db()
    assert sub.orden == 60 and sub.activa is False
