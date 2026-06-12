"""S-Checador-V1.2 — mapa (modal) de entrada/salida + recordatorio de
entrada no checada."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


# ── Mapa (modal) ──────────────────────────────────────────────────────────

def test_templatetags_osm_y_gmaps():
    from apps.checador.templatetags.checador_extras import gmaps_link, osm_embed_src, osm_link
    assert "openstreetmap.org/export/embed" in osm_embed_src(19.43, -99.13)
    assert "marker=19.43,-99.13" in osm_embed_src(19.43, -99.13)
    assert "google.com/maps" in gmaps_link(19.43, -99.13)
    assert "query=19.43,-99.13" in gmaps_link(19.43, -99.13)
    assert osm_embed_src(None, None) == ""
    assert gmaps_link("x", "y") == ""
    assert osm_link(19.43, -99.13).startswith("https://www.openstreetmap.org/")


def test_modal_mapa_con_coords(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/checador/mapa", {"lat": "19.43", "lng": "-99.13", "etiqueta": "Entrada"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "openstreetmap.org/export/embed" in body
    assert "google.com/maps" in body  # link a Google Maps
    assert "Entrada" in body


def test_modal_mapa_sin_coords(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/checador/mapa", {"etiqueta": "Salida"})
    assert resp.status_code == 200
    assert "Sin ubicación" in resp.content.decode()


def test_tablero_boton_mapa(client, usuario_factory):
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    Jornada.objects.create(
        usuario=u, fecha=timezone.localdate(),
        entrada_en=timezone.now(), entrada_lat=19.43, entrada_lng=-99.13,
    )
    client.force_login(u)
    resp = client.get("/checador/")
    assert "📍 Mapa" in resp.content.decode()


def test_equipo_persona_admin_ok_disenador_403(client, usuario_factory):
    from apps.checador.models import Jornada
    admin = usuario_factory(rol="super_admin")
    empleado = usuario_factory(rol="disenador")
    Jornada.objects.create(
        usuario=empleado, fecha=timezone.localdate(),
        entrada_en=timezone.now(), entrada_lat=19.43, entrada_lng=-99.13,
    )
    client.force_login(admin)
    resp = client.get(f"/checador/equipo/{empleado.pk}/")
    assert resp.status_code == 200
    assert "📍 Mapa" in resp.content.decode()

    client.force_login(empleado)  # un diseñador no ve el equipo
    assert client.get(f"/checador/equipo/{empleado.pk}/").status_code in (302, 403)


# ── Recordatorio de entrada ───────────────────────────────────────────────

def _horario(usuario, *, dia=0, entrada=(9, 0), tol=15):
    from apps.checador.models import HorarioLaboral
    return HorarioLaboral.objects.create(
        usuario=usuario, dia_semana=dia,
        hora_entrada=datetime.time(*entrada), hora_salida=datetime.time(18, 0),
        tolerancia_min=tol, activo=True,
    )


_LUNES_10 = None  # se calcula con tz en cada test


def _lunes(hora, minuto=0):
    # 2026-06-15 es lunes (weekday 0).
    return timezone.make_aware(datetime.datetime(2026, 6, 15, hora, minuto))


def test_recordatorio_se_envia_y_es_idempotente(usuario_factory, monkeypatch):
    import lib.interfono as interfono
    enviados = []
    monkeypatch.setattr(interfono, "enviar_a_usuario", lambda u, *a, **k: enviados.append(u.pk) or {})
    from apps.checador import services
    from apps.checador.models import RecordatorioEntrada
    u = usuario_factory(rol="disenador")
    _horario(u, dia=0)  # lunes 9:00 tol 15 → candidato + horario
    n = services.recordar_entradas_pendientes(ahora=_lunes(10, 0))
    assert n == 1 and u.pk in enviados
    assert RecordatorioEntrada.objects.filter(usuario=u, fecha=datetime.date(2026, 6, 15)).count() == 1
    # Segunda corrida el mismo día: no repite.
    enviados.clear()
    assert services.recordar_entradas_pendientes(ahora=_lunes(11, 0)) == 0
    assert enviados == []


def test_no_recuerda_si_ya_checo(usuario_factory, monkeypatch):
    import lib.interfono as interfono
    monkeypatch.setattr(interfono, "enviar_a_usuario", lambda *a, **k: {})
    from apps.checador import services
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    _horario(u, dia=0)
    Jornada.objects.create(usuario=u, fecha=datetime.date(2026, 6, 15), entrada_en=_lunes(9, 5))
    assert services.recordar_entradas_pendientes(ahora=_lunes(10, 0)) == 0


def test_no_recuerda_si_aun_no_es_tarde(usuario_factory, monkeypatch):
    import lib.interfono as interfono
    monkeypatch.setattr(interfono, "enviar_a_usuario", lambda *a, **k: {})
    from apps.checador import services
    u = usuario_factory(rol="disenador")
    _horario(u, dia=0)  # entrada 9:00 tol 15 → límite 9:15
    assert services.recordar_entradas_pendientes(ahora=_lunes(9, 5)) == 0
