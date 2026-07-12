"""LC Buzón §4 — combobox type-to-search + buscador/colapso del Kanban.

El combobox es JS (no unit-testeable sin navegador); aquí validamos el
CABLEADO server-side: que el atributo `data-select-buscable` se renderice en
los selects objetivo y que el Kanban traiga el buscador + los botones de
colapsar. El comportamiento JS (filtrado, panel) se prueba a mano.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_proyecto_form_cliente_combobox(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/proyectos/nuevo")
    assert resp.status_code == 200
    assert b"data-select-buscable" in resp.content  # cliente + producto/proveedor


def test_cotizacion_form_combobox(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/cotizaciones/nueva/")
    assert resp.status_code in (200, 302)
    if resp.status_code == 200:
        assert b"data-select-buscable" in resp.content


def test_kanban_buscador_y_colapso(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/proyectos/kanban/")
    assert resp.status_code == 200
    assert b"kanban-buscar" in resp.content       # input de búsqueda
    assert b"kanban-colapsar" in resp.content     # botón de colapsar columna
    assert b'data-buscar="' in resp.content or b"Sin proyectos" in resp.content
