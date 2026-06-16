"""S-Checador-V14 — POI de visita (cliente/proveedor/contacto), propósito
visita/tarea + verificación IA, snapshot de ubicación en sesiones de proyecto,
sede esperada (horario + corrección), y detalles clickeables."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _contacto(cliente):
    from apps.la_cartera.models import ClienteContacto
    return ClienteContacto.objects.create(cliente=cliente, nombre="Juan Pérez", principal=True)


# ── Visitas a POI: cliente / proveedor / contacto ─────────────────────────

def test_registrar_visita_contacto_deriva_cliente(usuario_factory, cliente_factory, monkeypatch):
    from apps.checador import services
    # No queremos disparar la IA en este test.
    monkeypatch.setattr("apps.checador.verificacion.verificar_visita_ia", lambda *a, **k: {"ok": False})
    u = usuario_factory(rol="disenador")
    cli = cliente_factory()
    co = _contacto(cli)
    v = services.registrar_visita(u, tipo="contacto", contacto=co, proposito="visita",
                                  geo={"lat": 19.4, "lng": -99.1, "sin_geo": False})
    assert v.contacto_id == co.pk
    assert v.cliente_id == cli.pk  # derivado del contacto
    assert v.proposito == "visita"
    assert "Juan Pérez" in v.destino


def test_registrar_visita_tarea_y_proposito(usuario_factory, proyecto_factory, monkeypatch):
    from apps.checador import services
    from apps.el_pizarron.models import Tarea
    monkeypatch.setattr("apps.checador.verificacion.verificar_visita_ia", lambda *a, **k: {"ok": False})
    u = usuario_factory(rol="disenador")
    pry = proyecto_factory()
    t = Tarea.objects.create(proyecto=pry, titulo="Recoger muestras", asignada_a=u)
    v = services.registrar_visita(u, tipo="otro", proposito="tarea", tarea=t,
                                  nota="Fui por las telas", geo={"sin_geo": True})
    assert v.proposito == "tarea"
    assert v.tarea_id == t.pk


def test_registrar_visita_contacto_sin_contacto_falla(usuario_factory):
    from apps.checador import services
    u = usuario_factory(rol="disenador")
    with pytest.raises(ValueError):
        services.registrar_visita(u, tipo="contacto", contacto=None)


# ── Verificación por El Chalán ────────────────────────────────────────────

def test_verificar_visita_ia_clasifica(usuario_factory, cliente_factory, monkeypatch):
    from apps.checador import services

    class _Res:
        texto = '{"proposito": "tarea", "completada": true, "confianza": 0.9, "resumen": "Recogió muestras"}'

    monkeypatch.setattr("lib.analistas.analizar", lambda **k: _Res())
    u = usuario_factory(rol="disenador")
    cli = cliente_factory()
    v = services.registrar_visita(u, tipo="cliente", cliente=cli, proposito="visita", nota="Recogí muestras")
    # registrar_visita programa la verificación en on_commit (inmediato por el fixture).
    v.refresh_from_db()
    assert v.ia_proposito == "tarea"
    assert v.ia_completada is True
    assert v.ia_confianza == 0.9
    assert v.proposito_efectivo == "tarea"  # el AI manda sobre lo marcado
    assert v.ia_verificado_en is not None


def test_verificar_sin_senal_no_corre(usuario_factory, cliente_factory, monkeypatch):
    from apps.checador import verificacion
    llamado = {"n": 0}

    def _fake(**k):
        llamado["n"] += 1
        raise AssertionError("no debió llamarse")

    monkeypatch.setattr("lib.analistas.analizar", _fake)
    u = usuario_factory(rol="disenador")
    cli = cliente_factory()
    from apps.checador.models import Visita
    v = Visita.objects.create(usuario=u, registrado_en=timezone.now(), tipo="cliente", cliente=cli)
    out = verificacion.verificar_visita_ia(v)
    assert out["ok"] is False
    assert llamado["n"] == 0


# ── Snapshot de ubicación en sesiones de proyecto ─────────────────────────

def test_timer_guarda_ubicacion(usuario_factory, proyecto_factory):
    from apps.checador import services
    u = usuario_factory(rol="disenador")
    pry = proyecto_factory()
    s = services.iniciar_timer(u, pry, geo={"lat": 19.5, "lng": -99.2, "precision": 12.0, "sin_geo": False})
    assert s.lat == 19.5 and s.lng == -99.2 and s.sin_geo is False
    assert s.maps_url


def test_captura_manual_guarda_ubicacion(usuario_factory, proyecto_factory):
    from apps.checador import services
    u = usuario_factory(rol="disenador")
    pry = proyecto_factory()
    ini = timezone.now() - datetime.timedelta(hours=2)
    fin = timezone.now() - datetime.timedelta(hours=1)
    s = services.capturar_sesion_manual(u, pry, inicio=ini, fin=fin,
                                        geo={"lat": 20.0, "lng": -99.0, "sin_geo": False})
    assert s.lat == 20.0 and s.duracion_min == 60


# ── Sede esperada (item 3): horario + corrección ──────────────────────────

def test_editar_jornada_directo_asigna_sede(usuario_factory):
    from apps.checador import services
    from apps.checador.models import SedeLC
    u = usuario_factory(rol="disenador")
    admin = usuario_factory(rol="super_admin")
    sede = SedeLC.objects.create(nombre="Oficina 1", lat=19.4, lng=-99.1)
    hoy = timezone.localdate()
    j = services.editar_jornada_directo(usuario=u, fecha=hoy, valor_entrada=timezone.now(),
                                        admin=admin, sede=sede)
    assert j.sede_id == sede.pk
    assert j.sede_label == "Oficina 1"


def test_ajuste_jornada_sede_texto_y_resolver_asigna_sede(usuario_factory, monkeypatch):
    from apps.checador import services
    from apps.checador.models import SedeLC
    monkeypatch.setattr(services, "_publicar_correccion_en_recados", lambda *a, **k: None)
    monkeypatch.setattr(services, "_publicar_resolucion_en_recados", lambda *a, **k: None)
    empleado = usuario_factory(rol="disenador")
    admin = usuario_factory(rol="super_admin")
    sede = SedeLC.objects.create(nombre="Taller Cuajimalpa")
    ayer = timezone.localdate() - datetime.timedelta(days=1)
    entrada = timezone.make_aware(datetime.datetime.combine(ayer, datetime.time(9, 0)))
    sol = services.solicitar_ajuste_jornada(
        empleado, fecha=ayer, valor_entrada=entrada, motivo="Olvidé checar",
        sede_texto="Taller (lo escribí yo)")
    assert sol.sede_texto == "Taller (lo escribí yo)"
    services.resolver_correccion(sol, admin=admin, aprobar=True, sede=sede)
    sol.refresh_from_db()
    from apps.checador.models import Jornada
    j = Jornada.objects.get(usuario=empleado, fecha=ayer)
    assert j.sede_id == sede.pk


# ── Detalles clickeables (item 2) ─────────────────────────────────────────

def test_detalle_jornada_propia_ok_ajena_403(client, usuario_factory):
    from apps.checador.models import Jornada
    dueno = usuario_factory(rol="disenador")
    otro = usuario_factory(rol="disenador")
    j = Jornada.objects.create(usuario=dueno, fecha=timezone.localdate(), entrada_en=timezone.now())
    client.force_login(dueno)
    assert client.get(f"/checador/jornada/{j.pk}/detalle").status_code == 200
    client.force_login(otro)
    assert client.get(f"/checador/jornada/{j.pk}/detalle").status_code == 403


def test_detalle_visita_super_admin_ve(client, usuario_factory, cliente_factory, monkeypatch):
    from apps.checador import services
    monkeypatch.setattr("apps.checador.verificacion.verificar_visita_ia", lambda *a, **k: {"ok": False})
    dueno = usuario_factory(rol="disenador")
    sa = usuario_factory(rol="super_admin")
    cli = cliente_factory()
    v = services.registrar_visita(dueno, tipo="cliente", cliente=cli, proposito="tarea", nota="x")
    client.force_login(sa)
    resp = client.get(f"/checador/visita/{v.pk}/detalle")
    assert resp.status_code == 200
    assert cli.razon_social in resp.content.decode()


# ── UI: modal de visita y tablero ─────────────────────────────────────────

def test_visita_modal_tiene_proposito_contacto_tarea(client, usuario_factory, cliente_factory):
    u = usuario_factory(rol="disenador")
    cliente_factory()
    client.force_login(u)
    body = client.get("/checador/visita/nueva").content.decode()
    assert 'name="proposito"' in body
    assert 'name="contacto"' in body
    assert 'name="tarea"' in body
    assert 'value="contacto"' in body  # tipo contacto


def test_tablero_boton_visita_y_gmaps(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    body = client.get("/checador/").content.decode()
    assert "Registrar visita / tarea" in body
    assert "Ver ubicación en Google Maps" in body
    assert 'data-ubicacion-gmaps="1"' in body


def test_visita_post_contacto_crea_registro(client, usuario_factory, cliente_factory, monkeypatch):
    monkeypatch.setattr("apps.checador.verificacion.verificar_visita_ia", lambda *a, **k: {"ok": False})
    from apps.checador.models import Visita
    u = usuario_factory(rol="disenador")
    cli = cliente_factory()
    co = _contacto(cli)
    client.force_login(u)
    resp = client.post("/checador/visita", {
        "tipo": "contacto", "contacto": str(co.pk), "proposito": "visita",
        "sin_geo": "1", "nota": "",
    })
    assert resp.status_code == 302
    v = Visita.objects.get(usuario=u)
    assert v.contacto_id == co.pk and v.cliente_id == cli.pk


def test_estacion_checador_visita_seeded():
    from chalanes.models import CuadroChalanes
    assert CuadroChalanes.objects.filter(estacion="checador_visita").exists()
