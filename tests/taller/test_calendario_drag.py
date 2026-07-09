"""D7 (LC 2026-07) — drag&drop: recolocar un evento a otro día."""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _proyecto(cli, autor):
    from apps.los_proyectos.models import Proyecto
    return Proyecto.objects.create(nombre="Feria", cliente=cli, creado_por=autor)


def test_mover_tarea_cambia_fecha(client, cliente_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea
    autor = usuario_factory(rol="super_admin")
    proy = _proyecto(cliente_factory(creado_por=autor), autor)
    t = Tarea.objects.create(proyecto=proy, titulo="X", asignada_a=autor,
                             fecha_compromiso=dt.date.today(), creado_por=autor)
    destino = (dt.date.today() + dt.timedelta(days=3)).isoformat()
    client.force_login(autor)
    resp = client.post("/calendario/mover/", {"tipo": "tarea", "id": str(t.pk), "fecha": destino})
    assert resp.status_code == 200 and resp.json()["ok"] is True
    t.refresh_from_db()
    assert t.fecha_compromiso.isoformat() == destino


def test_mover_proyecto_conserva_hora(client, cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    proy = _proyecto(cliente_factory(creado_por=autor), autor)
    proy.fecha_compromiso = timezone.make_aware(dt.datetime(2026, 7, 10, 15, 30))
    proy.save()
    destino = "2026-07-15"
    client.force_login(autor)
    resp = client.post("/calendario/mover/", {"tipo": "entrega", "id": str(proy.pk), "fecha": destino})
    assert resp.status_code == 200 and resp.json()["ok"] is True
    proy.refresh_from_db()
    local = timezone.localtime(proy.fecha_compromiso)
    assert local.date().isoformat() == destino
    assert local.hour == 15 and local.minute == 30


def test_mover_fecha_invalida_400(client, cliente_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea
    autor = usuario_factory(rol="super_admin")
    proy = _proyecto(cliente_factory(creado_por=autor), autor)
    t = Tarea.objects.create(proyecto=proy, titulo="X", asignada_a=autor, creado_por=autor)
    client.force_login(autor)
    resp = client.post("/calendario/mover/", {"tipo": "tarea", "id": str(t.pk), "fecha": "no-fecha"})
    assert resp.status_code == 400
