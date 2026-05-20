"""S2b.5 — Aprobación / rechazo de KPIs custom de alcance 'equipo' por super_admin."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def _crear_pendiente(autor, **kwargs):
    from apps.taller_home.models import KPICustom
    defaults = dict(
        slug=f"pend-{autor.pk}",
        titulo="KPI Pendiente",
        definicion_json={"entidad": "proyecto", "agregacion": "count",
                         "filtros": [], "ventana_tiempo": "siempre",
                         "alcance_usuario": "todos"},
        alcance="equipo",
        estado="pendiente_aprobacion",
        autor=autor,
    )
    defaults.update(kwargs)
    return KPICustom.objects.create(**defaults)


def test_lista_pendientes_solo_admin(client, usuario_factory):
    propone = usuario_factory(rol="contador")
    _crear_pendiente(propone)
    admin = usuario_factory(rol="super_admin", email="adm@x.com")
    client.force_login(admin)
    resp = client.get("/chalanes/kpis-pendientes/")
    assert resp.status_code == 200
    assert b"KPI Pendiente" in resp.content


def test_disenador_no_accede(client, usuario_factory):
    d = usuario_factory(rol="disenador")
    client.force_login(d)
    resp = client.get("/chalanes/kpis-pendientes/")
    assert resp.status_code in (302, 403)


def test_aprobar_activa_kpi(client, usuario_factory):
    autor = usuario_factory(rol="contador")
    kpi = _crear_pendiente(autor)
    admin = usuario_factory(rol="super_admin", email="adm@x.com")
    client.force_login(admin)
    resp = client.post(f"/chalanes/kpis-pendientes/{kpi.pk}/aprobar")
    assert resp.status_code == 302
    kpi.refresh_from_db()
    assert kpi.estado == "activo"
    assert kpi.aprobado_por_id == admin.pk
    assert kpi.aprobado_en is not None


def test_rechazar_guarda_motivo(client, usuario_factory):
    autor = usuario_factory(rol="contador")
    kpi = _crear_pendiente(autor)
    admin = usuario_factory(rol="super_admin", email="adm@x.com")
    client.force_login(admin)
    resp = client.post(f"/chalanes/kpis-pendientes/{kpi.pk}/rechazar", {"motivo": "duplica un KPI existente"})
    assert resp.status_code == 302
    kpi.refresh_from_db()
    assert kpi.estado == "rechazado"
    assert "duplica" in kpi.motivo_rechazo
