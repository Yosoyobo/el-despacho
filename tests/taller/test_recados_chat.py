"""Sprint S-Recados-Chat — smoke tests del flujo de chat."""

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _login(client, usuario_factory, **kw):
    u = usuario_factory(**kw)
    client.force_login(u)
    return u


def test_bandeja_vacia_ok(client, usuario_factory):
    _login(client, usuario_factory, rol="super_admin")
    resp = client.get("/recados/")
    assert resp.status_code == 200
    assert b"Aun" in resp.content or b"primera" in resp.content or b"Nueva" in resp.content


def test_crear_conversacion_directa(client, usuario_factory):
    autor = _login(client, usuario_factory, rol="super_admin", email="a@ej.com")
    otro = usuario_factory(rol="disenador", email="o@ej.com")
    resp = client.post("/recados/nueva/", {"tipo": "directa", "destinatario": str(otro.pk)})
    assert resp.status_code == 302
    from apps.recados.models import Conversacion
    conv = Conversacion.objects.get()
    assert conv.tipo == "directa"
    assert set(conv.participantes.values_list("id", flat=True)) == {autor.pk, otro.pk}


def test_directa_idempotente(client, usuario_factory):
    _login(client, usuario_factory, rol="super_admin", email="a@ej.com")
    otro = usuario_factory(rol="disenador", email="o@ej.com")
    client.post("/recados/nueva/", {"tipo": "directa", "destinatario": str(otro.pk)})
    client.post("/recados/nueva/", {"tipo": "directa", "destinatario": str(otro.pk)})
    from apps.recados.models import Conversacion
    assert Conversacion.objects.count() == 1


def test_enviar_mensaje_y_polling(client, usuario_factory, monkeypatch):
    # on_commit no fira con db wrap — patcheamos para correr inmediato.
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())

    autor = _login(client, usuario_factory, rol="super_admin", email="a@ej.com")
    otro = usuario_factory(rol="disenador", email="o@ej.com")
    client.post("/recados/nueva/", {"tipo": "directa", "destinatario": str(otro.pk)})
    from apps.recados.models import Conversacion, Mensaje
    conv = Conversacion.objects.get()

    resp = client.post(f"/recados/c/{conv.pk}/enviar", {"cuerpo": "Hola mundo"})
    assert resp.status_code == 200
    assert Mensaje.objects.filter(conversacion=conv, autor=autor).count() == 1

    # Polling: con desde_id=0 trae todo, con id alto no trae nada.
    m = Mensaje.objects.get()
    resp = client.get(f"/recados/c/{conv.pk}/mensajes", {"desde_id": "0"})
    assert resp.status_code == 200
    assert b"Hola mundo" in resp.content
    resp = client.get(f"/recados/c/{conv.pk}/mensajes", {"desde_id": str(m.pk)})
    assert resp.status_code == 200
    assert b"Hola mundo" not in resp.content


def test_no_participante_404(client, usuario_factory):
    autor = usuario_factory(rol="super_admin", email="a@ej.com")
    otro = usuario_factory(rol="disenador", email="o@ej.com")
    from apps.recados.services_chat import obtener_o_crear_directa
    conv = obtener_o_crear_directa(autor, otro)
    intruso = usuario_factory(rol="contador", email="x@ej.com")
    client.force_login(intruso)
    assert client.get(f"/recados/c/{conv.pk}/").status_code == 404


def test_grupo_crea_y_envia(client, usuario_factory, monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())

    autor = _login(client, usuario_factory, rol="super_admin", email="a@ej.com")
    a = usuario_factory(rol="disenador", email="b@ej.com")
    b = usuario_factory(rol="contador", email="c@ej.com")
    resp = client.post("/recados/nueva/", {
        "tipo": "grupo", "nombre": "Equipo X",
        "participantes": [str(a.pk), str(b.pk)],
    })
    assert resp.status_code == 302
    from apps.recados.models import Conversacion
    conv = Conversacion.objects.get()
    assert conv.tipo == "grupo"
    assert conv.nombre == "Equipo X"
    assert set(conv.participantes.values_list("id", flat=True)) == {autor.pk, a.pk, b.pk}


def test_total_no_leidos(client, usuario_factory, monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())

    autor = usuario_factory(rol="super_admin", email="a@ej.com")
    otro = usuario_factory(rol="disenador", email="o@ej.com")
    from apps.recados.services_chat import (
        enviar_mensaje,
        obtener_o_crear_directa,
        total_no_leidos,
    )
    conv = obtener_o_crear_directa(autor, otro)
    enviar_mensaje(conversacion=conv, autor=autor, cuerpo="ping")
    enviar_mensaje(conversacion=conv, autor=autor, cuerpo="pong")
    assert total_no_leidos(otro) == 2
    assert total_no_leidos(autor) == 0  # sus propios mensajes no cuentan
