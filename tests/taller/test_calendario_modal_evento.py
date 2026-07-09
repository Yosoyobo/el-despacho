"""D6 (LC 2026-07) — modal corto de edición de tarea desde el calendario."""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _tarea(cli, autor):
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.models import Proyecto
    proy = Proyecto.objects.create(nombre="Museo", cliente=cli, creado_por=autor)
    return Tarea.objects.create(proyecto=proy, titulo="Cortar vinil", asignada_a=autor,
                                estado="pendiente", fecha_compromiso=dt.date.today(), creado_por=autor)


def test_modal_rapido_get(client, cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    t = _tarea(cliente_factory(creado_por=autor), autor)
    client.force_login(autor)
    resp = client.get(f"/tareas/{t.pk}/editar-rapido", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert b"Editar tarea" in resp.content
    # Modal corto: NO trae el hilo de comentarios.
    assert b"Comentarios" not in resp.content


def test_modal_rapido_guarda(client, cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    t = _tarea(cliente_factory(creado_por=autor), autor)
    client.force_login(autor)
    resp = client.post(
        f"/tareas/{t.pk}/editar-rapido",
        {"titulo": "Cortar vinil premium", "estado": "pendiente", "prioridad": "alta"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    assert "HX-Redirect" in resp
    t.refresh_from_db()
    assert t.titulo == "Cortar vinil premium"
    assert t.prioridad == "alta"


def test_dia_modal_lista_evento_como_boton_editable(client, cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    t = _tarea(cliente_factory(creado_por=autor), autor)
    client.force_login(autor)
    hoy = dt.date.today().isoformat()
    resp = client.get(f"/calendario/dia/{hoy}/", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    # El evento-tarea del día abre el modal rápido (hx-get), no un <a href> a la página.
    assert f"/tareas/{t.pk}/editar-rapido".encode() in resp.content
