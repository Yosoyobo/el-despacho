"""S-LC-Buzon-V2 (C5d): hilo de comentarios autor↔admin + toggle."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _msg(autor):
    from buzon.models import MensajeBuzon
    return MensajeBuzon.objects.create(autor=autor, tipo="otro", asunto="A", cuerpo="x" * 20)


def test_admin_comenta(client, usuario_factory):
    from buzon.models import MensajeBuzonComentario
    admin = usuario_factory(rol="super_admin")
    autor = usuario_factory(rol="disenador")
    m = _msg(autor)
    client.force_login(admin)
    resp = client.post(f"/buzon/{m.pk}/comentar", data={"cuerpo": "Lo revisamos pronto"})
    assert resp.status_code in (302, 200)
    assert MensajeBuzonComentario.objects.filter(mensaje=m, autor=admin).exists()


def test_autor_no_comenta_con_toggle_off(client, usuario_factory):
    from buzon.models import MensajeBuzonComentario
    autor = usuario_factory(rol="disenador")
    m = _msg(autor)
    client.force_login(autor)
    resp = client.post(f"/buzon/{m.pk}/comentar", data={"cuerpo": "gracias"})
    assert resp.status_code == 403
    assert not MensajeBuzonComentario.objects.filter(mensaje=m).exists()


def test_autor_comenta_con_toggle_on(client, usuario_factory):
    from buzon.models import ConfiguracionBuzon, MensajeBuzonComentario
    cfg = ConfiguracionBuzon.obtener()
    cfg.empleado_puede_responder = True
    cfg.save()
    autor = usuario_factory(rol="disenador")
    m = _msg(autor)
    client.force_login(autor)
    resp = client.post(f"/buzon/{m.pk}/comentar", data={"cuerpo": "gracias"})
    assert resp.status_code in (302, 200)
    assert MensajeBuzonComentario.objects.filter(mensaje=m, autor=autor).exists()


def test_ajeno_no_comenta(client, usuario_factory):
    autor = usuario_factory(rol="disenador")
    ajeno = usuario_factory(rol="disenador")
    m = _msg(autor)
    client.force_login(ajeno)
    resp = client.post(f"/buzon/{m.pk}/comentar", data={"cuerpo": "intruso"})
    assert resp.status_code == 404
