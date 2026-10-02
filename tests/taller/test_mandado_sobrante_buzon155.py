"""Buzón #155/#165 — una tarea que deja de ser entrega suelta su mandado.

La tarea «MENUS AZULES» nació como entrega, se cambió a tarea normal y su
Mandado se quedó vivo en «asignado»: el Dashboard la siguió mostrando en
«Mis mandados» aun después de completarla.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _entrega_asignada(proyecto_factory, usuario_factory, email="runner155@lc.mx"):
    from apps.el_pizarron import runners
    from apps.el_pizarron.models import Tarea
    p = proyecto_factory(estado="en_proceso_diseno")
    runner = usuario_factory(rol="disenador", email=email)
    t = Tarea.objects.create(proyecto=p, titulo="MENUS AZULES", tipo="entrega", estado="pendiente")
    runners.asignar_runner(t, runner)
    t.refresh_from_db()
    return t, runner


def test_cambiar_a_tarea_normal_borra_el_mandado_que_no_salio(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Mandado
    t, _ = _entrega_asignada(proyecto_factory, usuario_factory)
    assert Mandado.objects.get(tarea=t).estado == "asignado"
    t.tipo = "tarea"
    t.save()
    assert not Mandado.objects.filter(tarea=t).exists()


def test_volver_a_entrega_crea_uno_limpio(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Mandado
    t, _ = _entrega_asignada(proyecto_factory, usuario_factory)
    t.tipo = "tarea"
    t.save()
    t.tipo = "entrega"
    t.save()
    assert Mandado.objects.get(tarea=t).estado == "asignado"


def test_el_que_iba_en_camino_se_cancela_y_el_entregado_se_queda(proyecto_factory, usuario_factory):
    from apps.el_pizarron import mandados as svc
    from apps.el_pizarron.models import Mandado
    t, _ = _entrega_asignada(proyecto_factory, usuario_factory)
    svc.marcar_en_camino(Mandado.objects.get(tarea=t))
    t.tipo = "tarea"
    t.save()
    assert Mandado.objects.get(tarea=t).estado == "cancelado"

    t2, _ = _entrega_asignada(proyecto_factory, usuario_factory, email="runner155b@lc.mx")
    t2.estado = "completada"
    t2.save()
    t2.tipo = "tarea"
    t2.save()
    assert Mandado.objects.get(tarea=t2).estado == "entregado"


def test_mis_mandados_ignora_la_tarea_que_ya_no_es_entrega(proyecto_factory, usuario_factory):
    """Aunque el mandado sobreviviera (dato viejo), el Dashboard mira la tarea."""
    from apps.el_pizarron.models import Tarea
    from apps.taller_home.views import _mis_mandados
    t, runner = _entrega_asignada(proyecto_factory, usuario_factory)
    assert [m.tarea_id for m in _mis_mandados(runner)] == [t.pk]
    # Simula el dato viejo de producción: cambiar el tipo sin pasar por la señal.
    Tarea.objects.filter(pk=t.pk).update(tipo="tarea")
    assert _mis_mandados(runner) == []


def test_mis_mandados_ignora_la_tarea_cerrada(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea
    from apps.taller_home.views import _mis_mandados
    t, runner = _entrega_asignada(proyecto_factory, usuario_factory)
    Tarea.objects.filter(pk=t.pk).update(estado="completada")
    assert _mis_mandados(runner) == []
