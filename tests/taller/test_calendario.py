"""Tests del Calendario (S-LC-Feedback-V1)."""

from datetime import date, timedelta

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_calendario_anonimo_redirige(client):
    resp = client.get("/calendario/")
    assert resp.status_code in (301, 302)


def test_calendario_admin_ve_meses(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/calendario/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Renderiza dos meses consecutivos.
    nombres_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    hoy = date.today()
    assert nombres_meses[hoy.month - 1] in body


def test_calendario_muestra_entrega_proyecto(client, usuario_factory, proyecto_factory):
    u = usuario_factory(rol="super_admin")
    target = date.today() + timedelta(days=5)
    proyecto_factory(nombre="ProyectoCal", fecha_compromiso=target)
    client.force_login(u)
    resp = client.get(f"/calendario/?year={target.year}&month={target.month}")
    assert resp.status_code == 200
    assert "ProyectoCal" in resp.content.decode()


def test_mini_cal_en_home(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Ver calendario completo" in body


def test_grid_mes_pure():
    from apps.calendario.services import grid_mes
    g = grid_mes(2026, 5)
    assert g["year"] == 2026 and g["month"] == 5
    assert 4 <= len(g["semanas"]) <= 6
    # Cada semana tiene 7 días.
    for s in g["semanas"]:
        assert len(s) == 7
