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


# ───────────────────────── visitas (E3) ─────────────────────────

def test_boton_visita_siempre_visible(client, usuario_factory):
    # S-Checador-V14: el botón de visita/tarea a POI NO depende de la jornada
    # (los POI no checan entrada/salida); está siempre disponible.
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert b"Registrar visita / tarea" in client.get("/checador/").content
    client.post("/checador/checar", {"accion": "entrada", "sin_geo": "1", "uuid": "e-1"})
    assert b"Registrar visita / tarea" in client.get("/checador/").content


def test_visita_modal_lista_clientes(client, usuario_factory, cliente_factory):
    u = usuario_factory(rol="disenador")
    cliente_factory(razon_social="Heladería La Michoacana")
    client.force_login(u)
    resp = client.get("/checador/visita/nueva")
    assert resp.status_code == 200
    assert b"Helader" in resp.content


def test_registrar_visita_cliente(client, usuario_factory, cliente_factory):
    from apps.checador.models import Visita
    u = usuario_factory(rol="disenador")
    cliente = cliente_factory()
    client.force_login(u)
    resp = client.post("/checador/visita", {
        "tipo": "cliente", "cliente": str(cliente.pk), "nota": "Entrega de arte",
        "lat": "19.4", "lng": "-99.1", "sin_geo": "0", "uuid": "vis-1",
    })
    assert resp.status_code == 302
    v = Visita.objects.get(usuario=u)
    assert v.cliente_id == cliente.pk
    assert v.tipo == "cliente"
    assert v.nota == "Entrega de arte"


def test_registrar_visita_proveedor(client, usuario_factory):
    from apps.checador.models import Visita
    from apps.el_catalogo.models import Proveedor
    u = usuario_factory(rol="disenador")
    prov = Proveedor.objects.create(razon_social="Imprenta Z")
    client.force_login(u)
    client.post("/checador/visita", {
        "tipo": "proveedor", "proveedor": str(prov.pk), "sin_geo": "1", "uuid": "vis-2",
    })
    v = Visita.objects.get(usuario=u)
    assert v.proveedor_id == prov.pk
    assert v.cliente_id is None


def test_registrar_visita_cliente_sin_cliente_no_crea(client, usuario_factory):
    from apps.checador.models import Visita
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    client.post("/checador/visita", {"tipo": "cliente", "sin_geo": "1", "uuid": "vis-3"})
    assert Visita.objects.filter(usuario=u).count() == 0
