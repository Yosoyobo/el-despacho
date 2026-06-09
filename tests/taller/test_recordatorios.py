"""Recordatorios de tareas por vencer + deep links (S-Chalanes-UX #4)."""

from __future__ import annotations

from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _config(**kw):
    from cuentas.models import ConfigRecordatorios
    c = ConfigRecordatorios.get_solo()
    for k, v in kw.items():
        setattr(c, k, v)
    c.save()
    return c


def _tarea(proyecto, asignada_a, fecha):
    from apps.el_pizarron.models import Tarea
    return Tarea.objects.create(
        proyecto=proyecto, titulo="Entregar arte", asignada_a=asignada_a,
        estado="pendiente", prioridad="media", fecha_compromiso=fecha,
    )


def _capturar(monkeypatch):
    enviados = []
    from apps.taller_home import push_handlers
    monkeypatch.setattr(
        push_handlers, "notificar_tarea_recordatorio",
        lambda tarea, usuario, **kw: enviados.append((tarea.pk, usuario.pk, kw.get("motivo"))),
    )
    return enviados


def test_deep_link_tarea_asignada_apunta_a_tarea(monkeypatch, usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Tarea
    admin = usuario_factory(rol="super_admin")
    asignada = usuario_factory(rol="disenador")
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="X", asignada_a=asignada,
                             estado="pendiente", prioridad="media")
    capturado = {}
    import lib.interfono as interfono
    monkeypatch.setattr(interfono, "enviar_a_usuario",
                        lambda usuario, **kw: capturado.update(url=kw.get("url")))
    # on_commit no fira dentro del rollback de pytest (Bug E §14): lo forzamos.
    from django.db import transaction
    monkeypatch.setattr(transaction, "on_commit",
                        lambda fn, using=None, robust=False: fn())
    from apps.taller_home.push_handlers import notificar_tarea_asignada
    notificar_tarea_asignada(t, admin)
    assert capturado.get("url") == f"/tareas/{t.pk}/"


def test_recordatorio_el_dia_al_asignado(monkeypatch, usuario_factory, proyecto_factory):
    _config(avisar_el_dia=True, avisar_vencidas=False, dias_antes_csv="",
            incluir_asignado=True, incluir_lider=False, incluir_admins=False)
    asignada = usuario_factory(rol="disenador")
    p = proyecto_factory()
    t = _tarea(p, asignada, date.today())
    enviados = _capturar(monkeypatch)
    call_command("recordar_tareas_por_vencer", stdout=StringIO())
    assert (t.pk, asignada.pk, "hoy") in enviados
    t.refresh_from_db()
    assert t.ultimo_recordatorio == date.today()


def test_recordatorio_vencida_y_no_repite_mismo_dia(monkeypatch, usuario_factory, proyecto_factory):
    _config(avisar_el_dia=True, avisar_vencidas=True, dias_antes_csv="",
            incluir_asignado=True, incluir_lider=False, incluir_admins=False)
    asignada = usuario_factory(rol="disenador")
    p = proyecto_factory()
    t = _tarea(p, asignada, date.today() - timedelta(days=3))
    enviados = _capturar(monkeypatch)
    call_command("recordar_tareas_por_vencer", stdout=StringIO())
    assert (t.pk, asignada.pk, "vencida") in enviados
    # Segunda corrida el mismo día → no repite.
    enviados.clear()
    call_command("recordar_tareas_por_vencer", stdout=StringIO())
    assert enviados == []


def test_recordatorio_vencida_off_no_envia(monkeypatch, usuario_factory, proyecto_factory):
    _config(avisar_el_dia=True, avisar_vencidas=False, dias_antes_csv="",
            incluir_asignado=True, incluir_lider=False, incluir_admins=False)
    asignada = usuario_factory(rol="disenador")
    p = proyecto_factory()
    _tarea(p, asignada, date.today() - timedelta(days=2))
    enviados = _capturar(monkeypatch)
    call_command("recordar_tareas_por_vencer", stdout=StringIO())
    assert enviados == []


def test_recordatorio_incluye_lider(monkeypatch, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoAsignacion
    _config(avisar_el_dia=True, avisar_vencidas=False, dias_antes_csv="",
            incluir_asignado=True, incluir_lider=True, incluir_admins=False)
    asignada = usuario_factory(rol="disenador")
    lider = usuario_factory(rol="disenador")
    p = proyecto_factory()
    ProyectoAsignacion.objects.create(proyecto=p, usuario=lider, rol_en_proyecto="lider")
    t = _tarea(p, asignada, date.today())
    enviados = _capturar(monkeypatch)
    call_command("recordar_tareas_por_vencer", stdout=StringIO())
    pks = {u for (_, u, _) in enviados}
    assert asignada.pk in pks and lider.pk in pks


def test_config_inactiva_no_envia(monkeypatch, usuario_factory, proyecto_factory):
    _config(activo=False)
    asignada = usuario_factory(rol="disenador")
    p = proyecto_factory()
    _tarea(p, asignada, date.today())
    enviados = _capturar(monkeypatch)
    call_command("recordar_tareas_por_vencer", stdout=StringIO())
    assert enviados == []


def test_anticipacion_dias_antes(monkeypatch, usuario_factory, proyecto_factory):
    _config(avisar_el_dia=False, avisar_vencidas=False, dias_antes_csv="2",
            incluir_asignado=True, incluir_lider=False, incluir_admins=False)
    asignada = usuario_factory(rol="disenador")
    p = proyecto_factory()
    t = _tarea(p, asignada, date.today() + timedelta(days=2))
    enviados = _capturar(monkeypatch)
    call_command("recordar_tareas_por_vencer", stdout=StringIO())
    assert (t.pk, asignada.pk, "antes") in enviados
