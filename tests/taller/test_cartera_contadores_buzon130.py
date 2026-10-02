"""Buzón #130 — los contadores de Clientes cuentan lo mismo que su filtro.

Antes «Clientes activos» contaba a todo cliente no archivado (prospectos e
inactivos incluidos) y su filtro sólo mostraba los de estado «activo». Tampoco
había tarjeta de prospectos ni de inactivos, y la de archivados no se picaba.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def padron(usuario_factory, cliente_factory):
    admin = usuario_factory(rol="super_admin")
    for estado, n in (("activo", 3), ("prospecto", 2), ("inactivo", 1)):
        for _ in range(n):
            cliente_factory(creado_por=admin, estado=estado)
    cliente_factory(creado_por=admin, estado="activo", activo=False)
    return admin


def test_cada_tarjeta_cuenta_lo_que_muestra_su_filtro(client, padron):
    client.force_login(padron)
    tarjetas = {k["slug"]: k for k in client.get("/cartera/").context["tarjetas_kpi"]}
    assert set(tarjetas) == {"con_proyectos", "activos", "prospectos", "inactivos", "archivados"}
    esperado = {"activos": 3, "prospectos": 2, "inactivos": 1, "archivados": 1, "con_proyectos": 0}
    for slug, n in esperado.items():
        assert tarjetas[slug]["valor"] == n, slug
        resp = client.get(f"/cartera/?ver={slug}")
        assert len(resp.context["clientes"]) == n, slug


def test_picar_la_tarjeta_activa_quita_el_filtro(client, padron):
    client.force_login(padron)
    tarjetas = {k["slug"]: k for k in client.get("/cartera/?ver=prospectos").context["tarjetas_kpi"]}
    assert tarjetas["prospectos"]["activo"] is True
    assert tarjetas["prospectos"]["link"] == "?"
    assert tarjetas["inactivos"]["link"] == "?ver=inactivos"
