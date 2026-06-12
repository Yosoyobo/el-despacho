"""S-Checador E6 — reporte de equipo, export CSV, KPIs, push."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

LUNES = datetime.date(2026, 6, 8)


def _dt(h, m, fecha=LUNES):
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(h, m)))


# ───────────────────────── reporte de equipo ─────────────────────────

def test_equipo_requiere_ver_equipo(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert client.get("/checador/equipo/").status_code == 403


def test_equipo_lista_actividad(client, usuario_factory):
    from apps.checador import services
    empleado = usuario_factory(rol="disenador")
    services.checar_entrada(empleado, registrado_en=_dt(9, 0))
    services.checar_salida(empleado, registrado_en=_dt(17, 0))
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get(f"/checador/equipo/?desde={LUNES}&hasta={LUNES}")
    assert resp.status_code == 200
    assert empleado.email.encode() in resp.content or (empleado.nombre_completo or "").encode() in resp.content


def test_export_csv_jornadas(client, usuario_factory):
    from apps.checador import services
    empleado = usuario_factory(rol="disenador")
    services.checar_entrada(empleado, registrado_en=_dt(9, 0))
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get(f"/checador/equipo/export?vista=jornadas&desde={LUNES}&hasta={LUNES}")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    cuerpo = resp.content.decode("utf-8-sig")
    assert "Usuario" in cuerpo and "Retardo" in cuerpo


def test_export_requiere_exportar(client, usuario_factory):
    """Diseñador no tiene `exportar` ni `ver_equipo` → 403."""
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert client.get("/checador/equipo/export?vista=jornadas").status_code == 403


# ───────────────────────── KPIs ─────────────────────────

def test_kpis_checador_en_catalogo():
    from apps.taller_home.kpis import KPIS
    slugs = {k.slug for k in KPIS}
    assert {"checador-horas-semana", "checador-retardos-mes",
            "checador-visitas-semana", "checador-horas-por-proyecto-top"} <= slugs


def test_kpi_horas_semana_calcula(usuario_factory):
    from apps.checador import services
    from apps.taller_home.kpis import KPIS
    u = usuario_factory(rol="disenador")
    services.checar_entrada(u, registrado_en=_dt(9, 0))
    services.checar_salida(u, registrado_en=_dt(13, 0))  # 4 h (si LUNES es esta semana real puede variar)
    kpi = next(k for k in KPIS if k.slug == "checador-horas-semana")
    res = kpi.calcular(u)
    assert "valor" in res and res["link"] == "/checador/historial/"


# ───────────────────────── push ─────────────────────────

def test_push_categoria_checador_existe():
    from apps.perfil_notificaciones.views import CATEGORIAS
    slugs = {c[0] for c in CATEGORIAS}
    assert "checador" in slugs


def test_solicitud_pushea_a_aprobadores(monkeypatch, usuario_factory):
    """Al solicitar corrección se notifica a quien puede aprobar (no al autor)."""
    from apps.checador import services
    enviados = []
    import lib.interfono as interfono
    monkeypatch.setattr(interfono, "enviar_a_usuario",
                        lambda usuario, *a, **k: enviados.append(usuario.pk) or {})
    # on_commit corre inmediato bajo el rollback de pytest:
    from django.db import transaction
    monkeypatch.setattr(transaction, "on_commit", lambda fn, using=None, robust=False: fn())

    empleado = usuario_factory(rol="disenador")
    admin = usuario_factory(rol="super_admin")
    j = services.checar_entrada(empleado, registrado_en=_dt(9, 40))
    services.solicitar_correccion(empleado, tipo="entrada", valor_propuesto=_dt(9, 5), motivo="x", jornada=j)
    assert admin.pk in enviados
    assert empleado.pk not in enviados
