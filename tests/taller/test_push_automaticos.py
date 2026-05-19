"""S2b.4 — Push automáticos (buzon, proyectos, tareas) + opt-out."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def _patch_oncommit(monkeypatch):
    """pytest-django envuelve cada test en transacción que hace rollback;
    `transaction.on_commit` no firarí naturalmente. Lo forzamos inline."""
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _capturar_envios(monkeypatch):
    """Captura calls a lib.interfono.enviar_a_usuario en push_handlers."""
    capturas: list[dict] = []

    def fake(usuario, **kwargs):
        capturas.append({"usuario_id": usuario.pk, **kwargs})
        return {"entregadas": 0, "fallidas": 0, "invalidadas": 0, "entrega_id": 1}

    from apps.taller_home import push_handlers
    monkeypatch.setattr("lib.interfono.enviar_a_usuario", fake)
    # también monkeypatch el módulo que importa
    if hasattr(push_handlers, "enviar_a_usuario"):
        monkeypatch.setattr(push_handlers, "enviar_a_usuario", fake)
    return capturas


# ── Buzón ──


def test_push_buzon_nuevo_va_a_admins(monkeypatch, usuario_factory):
    _patch_oncommit(monkeypatch)
    capturas = _capturar_envios(monkeypatch)
    from apps.taller_home.push_handlers import notificar_buzon_nuevo

    from buzon.models import MensajeBuzon

    autor = usuario_factory(rol="disenador")
    a1 = usuario_factory(rol="dueno")
    a2 = usuario_factory(rol="super_admin")
    msg = MensajeBuzon.objects.create(autor=autor, tipo="problema", asunto="x", cuerpo="y")

    notificar_buzon_nuevo(msg, autor)
    ids = {c["usuario_id"] for c in capturas}
    assert {a1.pk, a2.pk} <= ids
    assert autor.pk not in ids  # el autor no recibe


def test_push_buzon_categoria_correcta(monkeypatch, usuario_factory):
    _patch_oncommit(monkeypatch)
    capturas = _capturar_envios(monkeypatch)
    from apps.taller_home.push_handlers import notificar_buzon_nuevo

    from buzon.models import MensajeBuzon

    autor = usuario_factory()
    usuario_factory(rol="dueno")
    msg = MensajeBuzon.objects.create(autor=autor, tipo="sugerencia", asunto="x", cuerpo="y")
    notificar_buzon_nuevo(msg, autor)
    assert all(c["categoria"] == "buzon" for c in capturas)


# ── Proyectos ──


def test_push_proyecto_creado_va_a_admins(monkeypatch, usuario_factory, proyecto_factory):
    _patch_oncommit(monkeypatch)
    capturas = _capturar_envios(monkeypatch)
    from apps.taller_home.push_handlers import notificar_proyecto_creado

    creador = usuario_factory(rol="dueno")
    a2 = usuario_factory(rol="super_admin")
    p = proyecto_factory(creado_por=creador)
    notificar_proyecto_creado(p, creador)
    ids = {c["usuario_id"] for c in capturas}
    assert a2.pk in ids
    assert creador.pk not in ids


def test_push_proyecto_status_va_a_asignados_no_actor(monkeypatch, usuario_factory, proyecto_factory):
    _patch_oncommit(monkeypatch)
    capturas = _capturar_envios(monkeypatch)
    from apps.los_proyectos.models import ProyectoAsignacion
    from apps.taller_home.push_handlers import notificar_proyecto_status_cambiado

    actor = usuario_factory(rol="dueno")
    asignado = usuario_factory(rol="disenador")
    p = proyecto_factory()
    ProyectoAsignacion.objects.create(proyecto=p, usuario=asignado, rol_en_proyecto="disenador")
    ProyectoAsignacion.objects.create(proyecto=p, usuario=actor, rol_en_proyecto="lider")

    notificar_proyecto_status_cambiado(p, "prospecto", "en_diseno", actor)
    ids = {c["usuario_id"] for c in capturas}
    assert asignado.pk in ids
    assert actor.pk not in ids


# ── Tareas ──


def test_push_tarea_asignada_va_al_asignada_a(monkeypatch, usuario_factory, proyecto_factory):
    _patch_oncommit(monkeypatch)
    capturas = _capturar_envios(monkeypatch)
    from apps.el_pizarron.models import Tarea
    from apps.taller_home.push_handlers import notificar_tarea_asignada

    actor = usuario_factory(rol="dueno")
    asignada = usuario_factory(rol="disenador")
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="x", asignada_a=asignada, creado_por=actor)

    notificar_tarea_asignada(t, actor)
    assert len(capturas) == 1
    assert capturas[0]["usuario_id"] == asignada.pk
    assert capturas[0]["categoria"] == "tareas"


def test_push_tarea_sin_asignar_no_dispara(monkeypatch, usuario_factory, proyecto_factory):
    _patch_oncommit(monkeypatch)
    capturas = _capturar_envios(monkeypatch)
    from apps.el_pizarron.models import Tarea
    from apps.taller_home.push_handlers import notificar_tarea_asignada

    actor = usuario_factory(rol="dueno")
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="x", creado_por=actor)  # sin asignada_a
    notificar_tarea_asignada(t, actor)
    assert capturas == []


def test_push_tarea_asignada_a_si_mismo_no_dispara(monkeypatch, usuario_factory, proyecto_factory):
    _patch_oncommit(monkeypatch)
    capturas = _capturar_envios(monkeypatch)
    from apps.el_pizarron.models import Tarea
    from apps.taller_home.push_handlers import notificar_tarea_asignada

    actor = usuario_factory(rol="dueno")
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="x", asignada_a=actor, creado_por=actor)
    notificar_tarea_asignada(t, actor)
    assert capturas == []


# ── Categorías visibles por rol ──


def test_perfil_notificaciones_admin_ve_categoria_buzon(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get("/perfil/notificaciones/")
    assert b"El Buz" in resp.content


def test_perfil_notificaciones_disenador_no_ve_categoria_buzon(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/perfil/notificaciones/")
    # La categoría 'buzon' está restringida a admin/dueno; diseñador no la ve.
    assert b'name="categoria" value="buzon"' not in resp.content
