"""S-Checador E4 — timer de proyecto, captura manual, historial."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_timer_iniciar_y_detener(client, usuario_factory, proyecto_factory):
    from apps.checador.models import SesionProyecto
    u = usuario_factory(rol="super_admin")  # ve todos los proyectos
    p = proyecto_factory()
    client.force_login(u)
    client.post("/checador/timer/iniciar", {"proyecto": str(p.pk)})
    assert SesionProyecto.objects.filter(usuario=u, estado="activa").count() == 1
    # El tablero muestra el cronómetro.
    assert b"cronometro" in client.get("/checador/").content
    client.post("/checador/timer/detener", {})
    assert SesionProyecto.objects.filter(usuario=u, estado="activa").count() == 0
    assert SesionProyecto.objects.filter(usuario=u, estado="cerrada").count() == 1


def test_timer_iniciar_proyecto_invalido(client, usuario_factory):
    from apps.checador.models import SesionProyecto
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    client.post("/checador/timer/iniciar", {"proyecto": "99999"})
    assert SesionProyecto.objects.filter(usuario=u).count() == 0


def test_disenador_no_ve_proyecto_ajeno_en_timer(client, usuario_factory, proyecto_factory):
    """Un diseñador no puede iniciar timer en un proyecto al que no está asignado."""
    from apps.checador.models import SesionProyecto
    u = usuario_factory(rol="disenador")
    p = proyecto_factory()  # sin asignar a u
    client.force_login(u)
    client.post("/checador/timer/iniciar", {"proyecto": str(p.pk)})
    assert SesionProyecto.objects.filter(usuario=u).count() == 0


def test_sesion_manual_modal(client, usuario_factory, proyecto_factory):
    u = usuario_factory(rol="super_admin")
    proyecto_factory(nombre="Branding ACME")
    client.force_login(u)
    resp = client.get("/checador/sesion/nueva")
    assert resp.status_code == 200
    assert b"Captura manual" in resp.content


def test_sesion_manual_crea(client, usuario_factory, proyecto_factory):
    from apps.checador.models import SesionProyecto
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    client.force_login(u)
    client.post("/checador/sesion", {
        "proyecto": str(p.pk),
        "inicio": "2026-06-08T10:00",
        "fin": "2026-06-08T12:30",
        "nota": "Diseño de logo",
    })
    s = SesionProyecto.objects.get(usuario=u, origen="manual")
    assert s.duracion_min == 150
    assert s.estado == "cerrada"


def test_sesion_manual_fin_antes_inicio_no_crea(client, usuario_factory, proyecto_factory):
    from apps.checador.models import SesionProyecto
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    client.force_login(u)
    client.post("/checador/sesion", {
        "proyecto": str(p.pk), "inicio": "2026-06-08T12:00", "fin": "2026-06-08T11:00",
    })
    assert SesionProyecto.objects.filter(usuario=u).count() == 0


def test_historial_muestra_totales(client, usuario_factory, proyecto_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/checador/historial/")
    assert resp.status_code == 200
    assert b"Mi historial" in resp.content
    assert b"horas en proyectos" in resp.content
