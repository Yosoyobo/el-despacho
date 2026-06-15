"""S-LC-Feedback-V10 — avisos de pendiente cumplido (fecha+hora) + contador rojo."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _tarea_vencida(proyecto, asignado, tipo="entrega"):
    from apps.el_pizarron.models import Tarea
    ayer = timezone.localdate() - datetime.timedelta(days=1)
    return Tarea.objects.create(
        proyecto=proyecto, titulo="Playera bordada", tipo=tipo,
        fecha_compromiso=ayer, hora=datetime.time(9, 0),
        asignada_a=asignado, creado_por=asignado,
    )


def test_avisa_entrega_con_texto_correcto(proyecto_factory, usuario_factory):
    from django.core.management import call_command

    from interfono.models import InterfonoEntrega
    u = usuario_factory(rol="disenador")
    p = proyecto_factory()
    t = _tarea_vencida(p, u, tipo="entrega")
    call_command("avisar_pendientes_cumplidos")
    entregas = InterfonoEntrega.objects.filter(usuario=u, origen_id=t.pk)
    assert entregas.exists()
    assert "Entrega:" in entregas.first().titulo
    t.refresh_from_db()
    assert t.aviso_cumplido_en is not None


def test_avisa_vencido_para_tarea_normal(proyecto_factory, usuario_factory):
    from django.core.management import call_command

    from interfono.models import InterfonoEntrega
    u = usuario_factory(rol="disenador")
    t = _tarea_vencida(proyecto_factory(), u, tipo="tarea")
    call_command("avisar_pendientes_cumplidos")
    e = InterfonoEntrega.objects.filter(usuario=u, origen_id=t.pk).first()
    assert e and "Vencido:" in e.titulo


def test_idempotente_no_duplica(proyecto_factory, usuario_factory):
    from django.core.management import call_command

    from interfono.models import InterfonoEntrega
    u = usuario_factory(rol="disenador")
    t = _tarea_vencida(proyecto_factory(), u)
    call_command("avisar_pendientes_cumplidos")
    call_command("avisar_pendientes_cumplidos")
    assert InterfonoEntrega.objects.filter(usuario=u, origen_id=t.pk).count() == 1


def test_no_avisa_futuro(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea
    from django.core.management import call_command

    from interfono.models import InterfonoEntrega
    u = usuario_factory(rol="disenador")
    manana = timezone.localdate() + datetime.timedelta(days=1)
    t = Tarea.objects.create(
        proyecto=proyecto_factory(), titulo="Futuro", tipo="entrega",
        fecha_compromiso=manana, hora=datetime.time(9, 0),
        asignada_a=u, creado_por=u,
    )
    call_command("avisar_pendientes_cumplidos")
    assert not InterfonoEntrega.objects.filter(usuario=u, origen_id=t.pk).exists()


def test_contador_rojo_y_marca_visto(client, proyecto_factory, usuario_factory):
    from django.core.management import call_command

    from interfono.context_processors import notificaciones_no_leidas
    from interfono.models import InterfonoEntrega
    u = usuario_factory(rol="disenador")
    _tarea_vencida(proyecto_factory(), u)
    call_command("avisar_pendientes_cumplidos")
    assert InterfonoEntrega.objects.filter(usuario=u, visto_en__isnull=True).exists()

    class _Req:
        user = u
    assert notificaciones_no_leidas(_Req())["notificaciones_no_leidas"] >= 1
    # Abrir la página marca todo visto → contador a 0.
    client.force_login(u)
    client.get("/perfil/notificaciones/")
    assert notificaciones_no_leidas(_Req())["notificaciones_no_leidas"] == 0
