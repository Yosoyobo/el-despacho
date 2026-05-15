"""El Inventario de Endpoints (drf-spectacular Swagger UI) — solo super_admin."""

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


class TestInventarioEndpoints:

    def test_anonimo_redirigido_a_login(self, client):
        resp = client.get("/inventario-de-endpoints/")
        # SoloSuperAdmin con anonimo → 403 (DRF), o 302 si pasa por login_required.
        assert resp.status_code in (302, 403)

    def test_disenador_recibe_403(self, client, usuario_factory):
        u = usuario_factory(rol="disenador")
        client.force_login(u)
        resp = client.get("/inventario-de-endpoints/")
        assert resp.status_code == 403

    def test_dueno_recibe_403(self, client, usuario_factory):
        u = usuario_factory(rol="dueno")
        client.force_login(u)
        resp = client.get("/inventario-de-endpoints/")
        assert resp.status_code == 403

    def test_super_admin_ve_swagger(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        resp = client.get("/inventario-de-endpoints/")
        assert resp.status_code == 200

    def test_super_admin_ve_schema_yaml(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        resp = client.get("/inventario-de-endpoints/schema/")
        assert resp.status_code == 200
        # Debe ser YAML u OpenAPI JSON con el endpoint /api/info/
        body = resp.content.decode()
        assert "/api/info/" in body

    def test_api_info_super_admin(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        resp = client.get("/api/info/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.1.0-s2a"
        assert "modulos_publicados" in data

    def test_api_info_disenador_forbidden(self, client, usuario_factory):
        u = usuario_factory(rol="disenador")
        client.force_login(u)
        resp = client.get("/api/info/")
        assert resp.status_code == 403
