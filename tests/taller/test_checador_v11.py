"""S-Checador-V1.1 — contadores en vivo, historial con periodo, y
corrección respondida desde Recados (aprobar/rechazar en el chat)."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _dt(h, m):
    hoy = timezone.localdate()
    return timezone.make_aware(datetime.datetime(hoy.year, hoy.month, hoy.day, h, m))


# ── C1: contadores en vivo ────────────────────────────────────────────────

def test_tablero_cronometro_jornada(client, usuario_factory):
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    Jornada.objects.create(usuario=u, fecha=timezone.localdate(), entrada_en=_dt(9, 0))
    client.force_login(u)
    resp = client.get("/checador/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "data-cronometro" in body
    assert "Jornada corriendo" in body


# ── C3: historial con periodo + secciones siempre visibles ────────────────

def test_historial_periodo_mes_y_secciones(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/checador/historial/?periodo=mes")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Este mes" in body            # selector + subtítulo
    assert "Visitas" in body             # sección siempre presente
    assert "Tiempo por proyecto" in body
    assert "Sin visitas" in body         # empty state al no haber visitas


def test_historial_periodo_invalido_cae_a_semana(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/checador/historial/?periodo=xyz")
    assert resp.status_code == 200
    assert "Esta semana" in resp.content.decode()


# ── C2: corrección → Recados (aprobar/rechazar en el chat) ─────────────────

def _solicitar(req):
    from apps.checador import services
    j = services.checar_entrada(req, registrado_en=_dt(9, 40))
    return services.solicitar_correccion(
        req, tipo="entrada", valor_propuesto=_dt(9, 5), motivo="me marcó tarde", jornada=j,
    ), j


def test_solicitar_publica_en_recados(usuario_factory):
    from apps.recados.models import Mensaje
    admin = usuario_factory(rol="super_admin")
    req = usuario_factory(rol="disenador")
    sol, _ = _solicitar(req)
    msgs = list(Mensaje.objects.filter(correccion=sol))
    assert msgs, "debe crearse un mensaje de chat ligado a la corrección"
    conv = msgs[0].conversacion
    assert set(conv.participantes.values_list("pk", flat=True)) == {req.pk, admin.pk}


def test_resolver_chat_aprueba_y_responde(client, usuario_factory):
    from apps.recados.models import Mensaje
    admin = usuario_factory(rol="super_admin")
    req = usuario_factory(rol="disenador")
    sol, jornada = _solicitar(req)
    msg = Mensaje.objects.filter(correccion=sol).first()

    client.force_login(admin)
    resp = client.post(
        f"/checador/correcciones/{sol.pk}/resolver-chat",
        {"decision": "aprobar", "mensaje_id": str(msg.pk)},
    )
    assert resp.status_code == 200
    assert "Aprobada" in resp.content.decode()
    sol.refresh_from_db()
    assert sol.estado == "aprobada"
    jornada.refresh_from_db()
    assert jornada.entrada_en == _dt(9, 5)  # se aplicó el valor propuesto
    # respuesta publicada de vuelta en la conversación
    assert Mensaje.objects.filter(
        conversacion=msg.conversacion, cuerpo__icontains="aprobada",
    ).exists()


def test_resolver_chat_sin_permiso(client, usuario_factory):
    from apps.recados.models import Mensaje
    usuario_factory(rol="super_admin")  # un aprobador para que se cree el chat
    req = usuario_factory(rol="disenador")
    sol, _ = _solicitar(req)
    msg = Mensaje.objects.filter(correccion=sol).first()
    client.force_login(req)  # el solicitante NO puede aprobar
    resp = client.post(
        f"/checador/correcciones/{sol.pk}/resolver-chat",
        {"decision": "aprobar", "mensaje_id": str(msg.pk if msg else 0)},
    )
    assert resp.status_code in (302, 403)
    sol.refresh_from_db()
    assert sol.estado == "pendiente"
