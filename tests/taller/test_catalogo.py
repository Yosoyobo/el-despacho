"""El Catálogo — CRUD de servicios + categorías + permisos granulares.

Pre-S2b.2: movido de Gerencia a Taller. Permisos por `puede(user, "catalogo", X)`
en lugar de `requires_role`.
"""

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def categoria(db):
    from apps.el_catalogo.models import CategoriaServicio
    # La categoría "Diseño" ya queda sembrada por la migración LC; reusamos.
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Diseño", defaults={"orden": 10})
    return cat


class TestCatalogoLista:

    def test_anonimo_redirige(self, client):
        resp = client.get("/catalogo/")
        assert resp.status_code in (302, 403)

    def test_disenador_ve_nombres_sin_precios(self, client, usuario_factory, categoria):
        """Pre-S2b.2: diseñador tiene `catalogo.ver_nombres` por default,
        pero NO `catalogo.ver_precios` — ve la lista sin columna de precio."""
        from apps.el_catalogo.models import Servicio
        Servicio.objects.create(nombre="Logo", precio_base="1500.00", categoria=categoria)
        client.force_login(usuario_factory(rol="disenador"))
        resp = client.get("/catalogo/")
        assert resp.status_code == 200
        assert b"Logo" in resp.content
        # Precio no debe aparecer en el HTML.
        assert b"$ 1500.00" not in resp.content
        assert b"1500.00" not in resp.content

    def test_contador_lee(self, client, usuario_factory, categoria):
        from apps.el_catalogo.models import Servicio
        Servicio.objects.create(nombre="Logo", precio_base="1500.00", categoria=categoria)
        client.force_login(usuario_factory(rol="contador"))
        resp = client.get("/catalogo/")
        assert resp.status_code == 200
        assert b"Logo" in resp.content

    def test_admin_ve_lista(self, client, usuario_factory, categoria):
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.get("/catalogo/")
        assert resp.status_code == 200


class TestCatalogoCRUD:

    def test_contador_no_crea(self, client, usuario_factory, categoria):
        client.force_login(usuario_factory(rol="contador"))
        resp = client.post("/catalogo/nuevo", {
            "nombre": "Tarjeta", "unidad": "millar", "precio_base": "500.00", "categoria": categoria.pk, "activo": "on",
        })
        assert resp.status_code == 403

    def test_admin_crea(self, client, usuario_factory, categoria):
        from apps.el_catalogo.models import Servicio
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.post("/catalogo/nuevo", {
            "nombre": "Tarjeta de presentación",
            "unidad": "millar",
            "precio_base": "750.00",
            "categoria": categoria.pk,
            "activo": "on",
            "descripcion_default": "Papel couche 350g",
        })
        assert resp.status_code == 302
        assert Servicio.objects.filter(nombre="Tarjeta de presentación").exists()

    def test_admin_edita(self, client, usuario_factory, categoria):
        from apps.el_catalogo.models import Servicio
        srv = Servicio.objects.create(nombre="Original", precio_base="100.00", categoria=categoria)
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.post(f"/catalogo/{srv.pk}/editar", {
            "nombre": "Renombrado", "unidad": "pieza", "precio_base": "120.00",
            "categoria": categoria.pk, "activo": "on", "descripcion_default": "",
        })
        assert resp.status_code == 302
        srv.refresh_from_db()
        assert srv.nombre == "Renombrado"
        assert str(srv.precio_base) == "120.00"

    def test_admin_archiva_y_reactiva(self, client, usuario_factory, categoria):
        from apps.el_catalogo.models import Servicio
        srv = Servicio.objects.create(nombre="Archivable", precio_base="50.00", categoria=categoria)
        client.force_login(usuario_factory(rol="super_admin"))
        client.post(f"/catalogo/{srv.pk}/archivar")
        srv.refresh_from_db()
        assert srv.activo is False
        client.post(f"/catalogo/{srv.pk}/archivar")
        srv.refresh_from_db()
        assert srv.activo is True


class TestCategorias:

    def test_admin_crea_categoria(self, client, usuario_factory):
        from apps.el_catalogo.models import CategoriaServicio
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.post("/catalogo/categorias/nueva", {"nombre": "Bordado", "orden": "40", "activa": "on"})
        assert resp.status_code == 302
        assert CategoriaServicio.objects.filter(nombre="Bordado").exists()

    def test_nombre_unico(self, client, usuario_factory, categoria):
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.post("/catalogo/categorias/nueva", {"nombre": "Diseño", "orden": "20", "activa": "on"})
        # ModelForm rechaza por unique → 200 con errors
        assert resp.status_code == 200


def test_seed_idempotente(db):
    from apps.el_catalogo.models import CategoriaServicio
    from django.core.management import call_command

    # Suma de seed_catalogo (6) + migración LC (agrega "Diseño + Producción" extra).
    call_command("seed_catalogo")
    n1 = CategoriaServicio.objects.count()
    assert n1 >= 6
    call_command("seed_catalogo")
    assert CategoriaServicio.objects.count() == n1
