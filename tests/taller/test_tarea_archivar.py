"""LC Buzón §6 (#154) — archivar tareas: soft-hide reversible, sigue en métricas."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _tarea(proyecto_factory, usuario_factory, **kw):
    from apps.el_pizarron.models import Tarea
    p = kw.pop("proyecto", None) or proyecto_factory()
    return Tarea.objects.create(proyecto=p, titulo=kw.pop("titulo", "Tarea X"), **kw)


def test_archivar_toggle(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    t = _tarea(proyecto_factory, usuario_factory, asignada_a=admin)
    client.force_login(admin)
    # Archivar.
    resp = client.post(f"/tareas/{t.pk}/archivar")
    assert resp.status_code in (302, 303)
    t.refresh_from_db()
    assert t.archivada is True
    # Desarchivar (reversible).
    client.post(f"/tareas/{t.pk}/archivar")
    t.refresh_from_db()
    assert t.archivada is False


def test_archivada_oculta_del_kanban_y_lista(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    visible = _tarea(proyecto_factory, usuario_factory, titulo="Visible ABC", asignada_a=admin)
    oculta = _tarea(proyecto_factory, usuario_factory, titulo="Oculta XYZ", asignada_a=admin, archivada=True)
    client.force_login(admin)
    # Kanban (default: sin archivadas).
    kb = client.get("/tareas/?f=1").content
    assert b"Visible ABC" in kb
    assert b"Oculta XYZ" not in kb
    # Ver archivadas → solo la archivada.
    arch = client.get("/tareas/?f=1&archivadas=1").content
    assert b"Oculta XYZ" in arch
    assert b"Visible ABC" not in arch
    # Contador de archivadas visible en el tablero normal.
    assert b"Ver archivadas" in kb
    # Lista tabular: oculta la archivada.
    lst = client.get("/tareas/lista/").content
    assert b"Visible ABC" in lst
    assert b"Oculta XYZ" not in lst
    _ = (visible, oculta)


def test_archivada_sigue_en_metricas(usuario_factory, proyecto_factory):
    """La archivada NO se pierde: sigue contando en métricas (a diferencia de
    borrar). Ejemplo: el total de tareas del proyecto."""
    from apps.el_pizarron.models import Tarea
    p = proyecto_factory()
    _tarea(proyecto_factory, usuario_factory, proyecto=p, titulo="A")
    _tarea(proyecto_factory, usuario_factory, proyecto=p, titulo="B", archivada=True)
    assert Tarea.objects.filter(proyecto=p).count() == 2  # ambas siguen existiendo
