"""S-Chalan-Negocio-V1 — revisión del conocimiento del negocio en La Gerencia.

super_admin lista y activa/desactiva; el shadow `chalanes.ConocimientoNegocio`
apunta a la tabla `el_dictado_conocimiento_negocio`.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def _crear(**kwargs):
    from chalanes.models import ConocimientoNegocio
    defaults = dict(ambito="cobranza", observacion="Clientes pagan tarde",
                    activo=False, origen="chalan_destilado")
    defaults.update(kwargs)
    return ConocimientoNegocio.objects.create(**defaults)


def test_lista_visible_para_super_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    _crear(observacion="El margen de bordado es bajo")
    resp = client.get("/chalanes/conocimiento/")
    assert resp.status_code == 200
    assert b"margen de bordado" in resp.content


def test_toggle_activa(client, usuario_factory):
    from chalanes.models import ConocimientoNegocio
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    item = _crear()
    resp = client.post(f"/chalanes/conocimiento/{item.pk}/toggle")
    assert resp.status_code in (302, 200)
    item = ConocimientoNegocio.objects.get(pk=item.pk)
    assert item.activo is True


def test_disenador_sin_acceso(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/chalanes/conocimiento/")
    assert resp.status_code in (302, 403)
