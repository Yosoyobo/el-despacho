"""Metas de KPI en Los Ajustes: guardar, verlas de vuelta y borrarlas.

Hasta 2026-09-29 el guardado daba 500 en producción (la imagen de La
Gerencia no traía `apps.taller_home`) y el panel salía vacío sin avisar.
El hueco de la imagen lo cuida `test_gerencia_trae_lo_que_importa.py`;
éste cuida el viaje completo del formulario.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


@pytest.fixture
def admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin", email="metas@x.com")
    client.force_login(u)
    return u


def test_guardar_una_meta_la_persiste_y_el_panel_la_muestra(client, admin):
    from apps.taller_home.models import MetaKPI

    resp = client.post("/ajustes/metas-kpi/guardar", {
        "valor__ingresos-mes": "250,000",
        "periodo__ingresos-mes": "trimestre",
        "activa__ingresos-mes": "1",
    })
    assert resp.status_code == 302

    meta = MetaKPI.objects.get(kpi_slug="ingresos-mes")
    assert meta.valor == Decimal("250000")
    assert meta.periodo == "trimestre"
    assert meta.activa is True
    assert meta.actualizado_por == admin

    panel = client.get("/ajustes/metas-kpi/")
    assert panel.status_code == 200
    assert 'name="valor__ingresos-mes" value="250000.00"' in panel.content.decode()


def test_vaciar_el_valor_borra_la_meta(client, admin):
    from apps.taller_home.models import MetaKPI

    MetaKPI.objects.create(kpi_slug="egresos-mes", valor=Decimal("1000"))
    resp = client.post("/ajustes/metas-kpi/guardar", {"valor__egresos-mes": ""})
    assert resp.status_code == 302
    assert not MetaKPI.objects.filter(kpi_slug="egresos-mes").exists()


def test_un_valor_que_no_es_numero_no_truena(client, admin):
    from apps.taller_home.models import MetaKPI

    resp = client.post("/ajustes/metas-kpi/guardar", {"valor__utilidad-mes": "mucho"})
    assert resp.status_code == 302
    assert not MetaKPI.objects.filter(kpi_slug="utilidad-mes").exists()
