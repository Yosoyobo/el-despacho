"""Fase 4 (LC 2026-07) — varios responsables por tarea + eliminar físico + emoji tipo."""

from __future__ import annotations

import pytest
from django.db.models import Q

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _proyecto(cli, autor):
    from apps.los_proyectos.models import Proyecto
    return Proyecto.objects.create(nombre="P", cliente=cli, creado_por=autor)


def test_sincroniza_principal_en_responsables(cliente_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea
    autor = usuario_factory(rol="super_admin")
    a = usuario_factory(rol="disenador")
    proy = _proyecto(cliente_factory(creado_por=autor), autor)
    t = Tarea.objects.create(proyecto=proy, titulo="T", asignada_a=a, creado_por=autor)
    t.sincronizar_responsable_principal()
    assert a in t.responsables_todos
    assert t.responsables.filter(pk=a.pk).exists()


def test_mis_tareas_incluye_corresponsable(cliente_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea
    autor = usuario_factory(rol="super_admin")
    a = usuario_factory(rol="disenador")
    b = usuario_factory(rol="disenador")
    proy = _proyecto(cliente_factory(creado_por=autor), autor)
    t = Tarea.objects.create(proyecto=proy, titulo="T", asignada_a=a, creado_por=autor)
    t.responsables.add(b)
    # b NO es el principal pero es corresponsable → la tarea es "suya".
    mias_b = Tarea.objects.filter(Q(asignada_a=b) | Q(responsables=b)).distinct()
    assert t in mias_b


def test_emoji_tipo():
    from apps.el_pizarron.models import Tarea
    assert Tarea(tipo="recoger").emoji_tipo == "🛵"
    assert Tarea(tipo="tarea").emoji_tipo == "💻"
    assert Tarea(tipo="entrega").emoji_tipo == "📦"


def test_eliminar_tarea_fisico_admin(client, cliente_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea
    autor = usuario_factory(rol="super_admin")
    proy = _proyecto(cliente_factory(creado_por=autor), autor)
    t = Tarea.objects.create(proyecto=proy, titulo="Borrar", asignada_a=autor, creado_por=autor)
    pk = t.pk
    client.force_login(autor)
    resp = client.post(f"/tareas/{pk}/eliminar")
    assert resp.status_code in (301, 302)
    assert not Tarea.objects.filter(pk=pk).exists()


def test_eliminar_tarea_ajeno_prohibido(client, cliente_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea
    autor = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="disenador")
    proy = _proyecto(cliente_factory(creado_por=autor), autor)
    t = Tarea.objects.create(proyecto=proy, titulo="No tocar", asignada_a=autor, creado_por=autor)
    client.force_login(otro)
    resp = client.post(f"/tareas/{t.pk}/eliminar")
    assert resp.status_code == 403
    assert Tarea.objects.filter(pk=t.pk).exists()
