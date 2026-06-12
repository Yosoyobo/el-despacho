"""S-Checador E2 — vistas del tablero móvil (checada entrada/salida)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_tablero_pide_login(client):
    resp = client.get("/checador/")
    assert resp.status_code in (301, 302)


def test_tablero_sin_permiso_403(client, usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    u = usuario_factory(rol="disenador")
    # Revoca el permiso `checar` (override individual gana sobre el default).
    PermisoUsuario.objects.update_or_create(
        usuario=u, modulo="checador", permiso="checar", defaults={"activo": False},
    )
    client.force_login(u)
    resp = client.get("/checador/")
    assert resp.status_code == 403


def test_tablero_muestra_boton_entrada(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/checador/")
    assert resp.status_code == 200
    assert b"Registrar entrada" in resp.content


def test_checar_entrada_crea_jornada(client, usuario_factory):
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.post("/checador/checar", {
        "accion": "entrada", "lat": "19.43", "lng": "-99.13",
        "precision": "10", "sin_geo": "0", "uuid": "u-1",
    })
    assert resp.status_code == 302
    j = Jornada.objects.get(usuario=u)
    assert j.entrada_en is not None
    assert j.entrada_sin_geo is False
    assert j.entrada_lat == 19.43


def test_checar_entrada_sin_geo(client, usuario_factory):
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    client.post("/checador/checar", {"accion": "entrada", "sin_geo": "1", "uuid": "u-2"})
    j = Jornada.objects.get(usuario=u)
    assert j.entrada_sin_geo is True
    assert j.entrada_lat is None


def test_flujo_entrada_luego_salida(client, usuario_factory):
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    client.post("/checador/checar", {"accion": "entrada", "sin_geo": "1", "uuid": "e-1"})
    # El tablero ahora ofrece salida.
    resp = client.get("/checador/")
    assert b"Registrar salida" in resp.content
    client.post("/checador/checar", {"accion": "salida", "sin_geo": "1", "uuid": "s-1"})
    j = Jornada.objects.get(usuario=u)
    assert j.estado == "cerrada"
    assert j.salida_en is not None


def test_checar_get_no_permitido(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/checador/checar")
    assert resp.status_code == 405
