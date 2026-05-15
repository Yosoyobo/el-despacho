"""El Site — vistas + permisos. Mocks de chequeos en vivo."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


class TestAcceso:
    def test_anonimo_redirige(self, client):
        resp = client.get("/site/")
        assert resp.status_code in (302, 403)

    def test_disenador_403(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="disenador"))
        assert client.get("/site/").status_code == 403

    def test_contador_403(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="contador"))
        assert client.get("/site/").status_code == 403

    def test_dueno_ok(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="dueno"))
        assert client.get("/site/").status_code == 200

    def test_super_admin_ok(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        assert client.get("/site/").status_code == 200


class TestProbar:
    def _fake_ok(self):
        return {"estado": "ok", "latencia_ms": 100, "mensaje_error": None}

    def _fake_err(self):
        return {"estado": "error", "latencia_ms": 200, "mensaje_error": "boom"}

    def test_probar_desconocida_redirige(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.post("/site/probar/no_existe_xyz")
        assert resp.status_code == 302

    def test_probar_ok_guarda(self, client, usuario_factory):
        from apps.el_site.models import SiteChequeo
        client.force_login(usuario_factory(rol="super_admin"))
        with patch("apps.el_site.views.chequear", return_value=self._fake_ok()):
            resp = client.post("/site/probar/anthropic")
        assert resp.status_code == 302
        row = SiteChequeo.objects.first()
        assert row is not None
        assert row.plataforma == "anthropic"
        assert row.estado == "ok"
        assert row.origen == "manual"

    def test_probar_error_emite_evento(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        emitidos = []
        with patch("apps.el_site.views.chequear", return_value=self._fake_err()), \
             patch("apps.el_site.views.emitir", side_effect=lambda e: emitidos.append(e)):
            client.post("/site/probar/openai")
        assert len(emitidos) == 1
        assert emitidos[0].tipo == "site.integracion_fallo"
        assert emitidos[0].payload["plataforma"] == "openai"

    def test_probar_todas_corre_cada_plataforma(self, client, usuario_factory):
        from apps.el_site.models import SiteChequeo

        from lib.site.registry import PLATAFORMAS
        client.force_login(usuario_factory(rol="super_admin"))
        with patch("apps.el_site.views.chequear", return_value=self._fake_ok()):
            resp = client.post("/site/probar-todas")
        assert resp.status_code == 302
        assert SiteChequeo.objects.count() == len(PLATAFORMAS)

    def test_probar_htmx_devuelve_partial(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        with patch("apps.el_site.views.chequear", return_value=self._fake_ok()):
            resp = client.post("/site/probar/anthropic", HTTP_HX_REQUEST="true")
        assert resp.status_code == 200
        assert b"anthropic" in resp.content


class TestPartials:
    def test_partial_infra_solo_admin(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="disenador"))
        assert client.get("/site/partial/infra").status_code == 403
        client.force_login(usuario_factory(rol="dueno", email="d@x.com"))
        assert client.get("/site/partial/infra").status_code == 200

    def test_partial_integraciones(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        assert client.get("/site/partial/integraciones").status_code == 200

    def test_partial_internos(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        assert client.get("/site/partial/internos").status_code == 200


class TestAPI:
    """Endpoints DRF /api/site/* — auth + permission."""

    def test_snapshot_requiere_auth(self, client):
        resp = client.get("/api/site/")
        assert resp.status_code in (302, 401, 403)

    def test_snapshot_disenador_403(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="disenador"))
        assert client.get("/api/site/").status_code == 403

    def test_snapshot_super_admin_ok(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.get("/api/site/")
        assert resp.status_code == 200
        data = resp.json()
        assert "infra" in data
        assert "integraciones" in data
        assert "internos" in data

    def test_api_probar_plataforma_desconocida_404(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="dueno"))
        resp = client.post("/api/site/probar/no_existe_xyz")
        assert resp.status_code == 404


class TestSlotsAjustes:
    def test_do_api_token_listado(self):
        from ajustes.models.credencial import SLOTS_CREDENCIAL
        claves = {c[0] for c in SLOTS_CREDENCIAL}
        assert "do_api_token" in claves
        assert "n8n_health_url" in claves
