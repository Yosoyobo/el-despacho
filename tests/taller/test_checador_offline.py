"""S-Checador E7 — endpoint de sync de la cola offline."""

from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _post(client, items):
    return client.post("/checador/api/sync", data=json.dumps({"items": items}),
                       content_type="application/json")


def test_sync_aplica_entrada_offline(client, usuario_factory):
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = _post(client, [{
        "uuid": "off-1", "tipo": "entrada", "registrado_en": "2026-06-08T09:00:00",
        "sin_geo": True,
    }])
    assert resp.status_code == 200
    data = resp.json()
    assert data["resultados"][0]["ok"] is True
    j = Jornada.objects.get(usuario=u)
    assert j.entrada_offline is True


def test_sync_idempotente_por_uuid(client, usuario_factory):
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    item = {"uuid": "off-2", "tipo": "entrada", "registrado_en": "2026-06-08T09:00:00", "sin_geo": True}
    _post(client, [item])
    _post(client, [item])  # reintento del mismo uuid
    assert Jornada.objects.filter(usuario=u).count() == 1


def test_sync_lote_entrada_y_salida(client, usuario_factory):
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = _post(client, [
        {"uuid": "e", "tipo": "entrada", "registrado_en": "2026-06-08T09:00:00", "sin_geo": True},
        {"uuid": "s", "tipo": "salida", "registrado_en": "2026-06-08T17:00:00", "sin_geo": True},
    ])
    assert all(r["ok"] for r in resp.json()["resultados"])
    j = Jornada.objects.get(usuario=u)
    assert j.estado == "cerrada"


def test_sync_visita_offline(client, usuario_factory, cliente_factory):
    from apps.checador.models import Visita
    u = usuario_factory(rol="disenador")
    cliente = cliente_factory()
    client.force_login(u)
    resp = _post(client, [{
        "uuid": "v-off", "tipo": "visita", "visita_tipo": "cliente", "cliente": cliente.pk,
        "registrado_en": "2026-06-08T11:00:00", "sin_geo": True, "nota": "offline",
    }])
    assert resp.json()["resultados"][0]["ok"] is True
    v = Visita.objects.get(usuario=u)
    assert v.capturada_offline is True
    assert v.cliente_id == cliente.pk


def test_sync_item_invalido_reporta_error(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = _post(client, [{"uuid": "bad", "tipo": "salida", "registrado_en": "2026-06-08T17:00:00", "sin_geo": True}])
    r = resp.json()["resultados"][0]
    assert r["ok"] is False
    assert "entrada" in r["error"].lower()


def test_sync_requiere_login(client):
    resp = _post(client, [])
    assert resp.status_code in (301, 302)


def test_sync_json_invalido(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.post("/checador/api/sync", data="no-json", content_type="application/json")
    assert resp.status_code == 400
