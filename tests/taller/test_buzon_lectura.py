"""Buzón email-like: lectura por usuario + búsqueda + toolbar (S-Chalanes-UX #3)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _msg(autor, asunto="Asunto", cuerpo="Cuerpo largo.", tipo="otro"):
    from buzon.models import MensajeBuzon
    return MensajeBuzon.objects.create(autor=autor, tipo=tipo, asunto=asunto, cuerpo=cuerpo)


def test_abrir_detalle_marca_leido_por_usuario(client, usuario_factory):
    from buzon.models import LecturaBuzon
    admin = usuario_factory(rol="super_admin")
    autor = usuario_factory(rol="disenador")
    m = _msg(autor)
    client.force_login(admin)
    assert not LecturaBuzon.objects.filter(usuario=admin, mensaje=m).exists()
    resp = client.get(f"/buzon/{m.pk}/")
    assert resp.status_code == 200
    assert LecturaBuzon.objects.filter(usuario=admin, mensaje=m).exists()


def test_lectura_es_independiente_por_usuario(client, usuario_factory):
    from buzon.lecturas import contar_no_leidos
    from buzon.models import MensajeBuzon
    a1 = usuario_factory(rol="super_admin")
    a2 = usuario_factory(rol="dueno")
    autor = usuario_factory(rol="disenador")
    m = _msg(autor)
    client.force_login(a1)
    client.get(f"/buzon/{m.pk}/")  # a1 lo lee
    assert contar_no_leidos(a1, MensajeBuzon.objects.all()) == 0
    # a2 aún no lo ha leído.
    assert contar_no_leidos(a2, MensajeBuzon.objects.all()) == 1


def test_toggle_leido(client, usuario_factory):
    from buzon.models import LecturaBuzon
    admin = usuario_factory(rol="super_admin")
    autor = usuario_factory(rol="disenador")
    m = _msg(autor)
    client.force_login(admin)
    client.post(f"/buzon/{m.pk}/toggle-leido")
    assert LecturaBuzon.objects.filter(usuario=admin, mensaje=m).exists()
    client.post(f"/buzon/{m.pk}/toggle-leido")
    assert not LecturaBuzon.objects.filter(usuario=admin, mensaje=m).exists()


def test_bulk_marcar_leido_y_no_leido_mio(client, usuario_factory):
    from buzon.models import LecturaBuzon
    admin = usuario_factory(rol="super_admin")
    autor = usuario_factory(rol="disenador")
    m1, m2 = _msg(autor), _msg(autor)
    client.force_login(admin)
    client.post("/buzon/masivo", {"ids": [m1.pk, m2.pk], "accion": "marcar_leido_mio"})
    assert LecturaBuzon.objects.filter(usuario=admin).count() == 2
    client.post("/buzon/masivo", {"ids": [m1.pk, m2.pk], "accion": "marcar_no_leido_mio"})
    assert LecturaBuzon.objects.filter(usuario=admin).count() == 0


def test_busqueda_filtra(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    autor = usuario_factory(rol="disenador")
    _msg(autor, asunto="Cotización urgente")
    _msg(autor, asunto="Otra cosa")
    client.force_login(admin)
    resp = client.get("/buzon/?q=urgente")
    body = resp.content.decode()
    assert "Cotización urgente" in body
    assert "Otra cosa" not in body


def test_no_leidos_en_header(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    autor = usuario_factory(rol="disenador")
    _msg(autor)
    _msg(autor)
    client.force_login(admin)
    resp = client.get("/buzon/")
    assert resp.status_code == 200
    assert "sin leer" in resp.content.decode().lower()


def test_empleado_no_puede_toggle_ajeno(client, usuario_factory):
    a = usuario_factory(rol="disenador")
    b = usuario_factory(rol="disenador")
    m = _msg(b)
    client.force_login(a)
    resp = client.post(f"/recados/buzon/{m.pk}/leido/")
    assert resp.status_code == 404
