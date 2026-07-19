"""Tasas e Impuestos — sub-sección de Los Ajustes. Solo super_admin."""

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


class TestTasasUI:

    def test_anonimo_redirige(self, client):
        resp = client.get("/ajustes/tasas/")
        assert resp.status_code in (302, 403)

    def test_dueno_no_accede(self, client, usuario_factory):
        # super_admin only — los_ajustes regla #3
        client.force_login(usuario_factory(rol="dueno"))
        resp = client.get("/ajustes/tasas/")
        assert resp.status_code == 403

    def test_super_admin_ve_lista(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.get("/ajustes/tasas/")
        assert resp.status_code == 200

    def test_super_admin_crea_tasa(self, client, usuario_factory):
        from ajustes.models import TasaImpositiva
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.post("/ajustes/tasas/nueva", {
            "nombre": "IVA 16%", "porcentaje": "16.00", "tipo": "trasladado",
            "aplicable_default": "on", "activa": "on", "orden": "10",
        })
        assert resp.status_code == 302
        t = TasaImpositiva.objects.get(nombre="IVA 16%")
        assert t.tipo == "trasladado"
        assert t.aplicable_default is True

    def test_editar(self, client, usuario_factory):
        from decimal import Decimal

        from ajustes.models import TasaImpositiva
        t = TasaImpositiva.objects.create(
            nombre="Retención ISR", porcentaje=Decimal("10.00"), tipo="retencion", orden=30,
        )
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.post(f"/ajustes/tasas/{t.pk}/editar", {
            "nombre": "Retención ISR", "porcentaje": "1.25", "tipo": "retencion",
            "activa": "on", "orden": "30",
        })
        assert resp.status_code == 302
        t.refresh_from_db()
        # S-Finanzas-UX: el campo ahora guarda 4 decimales (1.25 → 1.2500).
        assert t.porcentaje == Decimal("1.25")
        assert t.porcentaje_str == "1.25"

    def test_editar_tasa_fraccionada_4_decimales(self, client, usuario_factory):
        """S-Finanzas-UX: tasas como 10.6667% (ret. IVA honorarios) se guardan
        con 4 decimales (antes el step=0.01 las bloqueaba)."""
        from decimal import Decimal

        from ajustes.models import TasaImpositiva
        t = TasaImpositiva.objects.create(
            nombre="Ret. IVA", porcentaje=Decimal("10.00"), tipo="retencion", orden=40,
        )
        client.force_login(usuario_factory(rol="super_admin"))
        resp = client.post(f"/ajustes/tasas/{t.pk}/editar", {
            "nombre": "Ret. IVA", "porcentaje": "10.6667", "tipo": "retencion",
            "activa": "on", "orden": "40",
        })
        assert resp.status_code == 302
        t.refresh_from_db()
        assert t.porcentaje == Decimal("10.6667")
        assert t.porcentaje_str == "10.6667"


def test_seed_tasas_idempotente(db):
    from django.core.management import call_command

    from ajustes.models import TasaImpositiva

    call_command("seed_tasas")
    n1 = TasaImpositiva.objects.count()
    assert n1 == 4
    iva = TasaImpositiva.objects.get(nombre="IVA 16%")
    assert iva.aplicable_default is True
    call_command("seed_tasas")
    assert TasaImpositiva.objects.count() == n1
