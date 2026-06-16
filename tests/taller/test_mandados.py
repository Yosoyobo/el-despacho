"""S-Chalan-Barrido parte 2 — entidad Mandado (companion 1:1 de Tarea).

La entrega/recolección sigue siendo una Tarea; el Mandado la acompaña con su
ciclo de reparto, creado/sincronizado por señal. Runner/destino viven en la
Tarea (cero regresión); el Mandado los expone y agrega estado logístico.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _tarea(proyecto, **kw):
    from apps.el_pizarron.models import Tarea
    defaults = dict(titulo="Entregar lona", tipo="entrega", estado="pendiente")
    defaults.update(kw)
    return Tarea.objects.create(proyecto=proyecto, **defaults)


def test_tarea_entrega_crea_mandado(proyecto_factory):
    from apps.el_pizarron.models import Mandado
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p)
    m = Mandado.objects.get(tarea=t)
    assert m.estado == "por_asignar"
    assert m.tipo == "entrega"
    assert m.proyecto == p


def test_tarea_normal_no_crea_mandado(proyecto_factory):
    from apps.el_pizarron.models import Mandado
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p, tipo="tarea")
    assert not Mandado.objects.filter(tarea=t).exists()


def test_asignar_runner_pasa_a_asignado(proyecto_factory, usuario_factory):
    from apps.el_pizarron import runners
    from apps.el_pizarron.models import Mandado
    p = proyecto_factory(estado="en_proceso_diseno")
    runner = usuario_factory(rol="disenador", email="r@lc.mx")
    t = _tarea(p)
    runners.asignar_runner(t, runner)
    m = Mandado.objects.get(tarea=t)
    assert m.estado == "asignado"
    assert m.asignado_en is not None
    assert m.runner_id == runner.pk


def test_completar_tarea_marca_entregado(proyecto_factory):
    from apps.el_pizarron.models import Mandado
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p)
    t.estado = "completada"  # terminal
    t.save()
    m = Mandado.objects.get(tarea=t)
    assert m.estado == "entregado"
    assert m.entregado_en is not None


def test_marcar_en_camino_y_entregado(proyecto_factory, usuario_factory):
    from apps.el_pizarron import mandados as svc
    from apps.el_pizarron import runners
    from apps.el_pizarron.models import Mandado
    p = proyecto_factory(estado="en_proceso_diseno")
    runner = usuario_factory(rol="disenador", email="r2@lc.mx")
    t = _tarea(p)
    runners.asignar_runner(t, runner)
    m = Mandado.objects.get(tarea=t)
    svc.marcar_en_camino(m)
    assert m.estado == "en_camino" and m.en_camino_en is not None
    svc.marcar_entregado(m)
    m.refresh_from_db()
    t.refresh_from_db()
    assert m.estado == "entregado"
    assert t.estado in {"completada"} or t.completada_en is not None  # la tarea se completó


def test_cancelar_gana_sobre_sync(proyecto_factory, usuario_factory):
    from apps.el_pizarron import mandados as svc
    from apps.el_pizarron import runners
    from apps.el_pizarron.models import Mandado
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p)
    m = Mandado.objects.get(tarea=t)
    svc.cancelar(m, motivo="cliente canceló")
    assert m.estado == "cancelado"
    # asignar runner después NO revive el mandado cancelado
    runners.asignar_runner(t, usuario_factory(rol="disenador", email="r3@lc.mx"))
    m.refresh_from_db()
    assert m.estado == "cancelado"


def test_fijar_destino_escribe_en_tarea(proyecto_factory):
    from apps.el_pizarron import mandados as svc
    from apps.el_pizarron.models import Mandado
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p)
    m = Mandado.objects.get(tarea=t)
    svc.fijar_destino(m, lat=19.40, lng=-99.16, etiqueta="Bodega")
    t.refresh_from_db()
    assert t.destino_lat == 19.40 and t.destino_lng == -99.16
    assert t.destino_etiqueta == "Bodega"


def test_mandados_visibles_row_level(proyecto_factory, usuario_factory):
    from apps.el_pizarron import runners
    from apps.el_pizarron.mandados import mandados_visibles
    p = proyecto_factory(estado="en_proceso_diseno")
    runner = usuario_factory(rol="disenador", email="ve@lc.mx")
    otro = usuario_factory(rol="disenador", email="otro@lc.mx")
    admin = usuario_factory(rol="super_admin", email="jefe@lc.mx")
    t = _tarea(p)
    runners.asignar_runner(t, runner)
    assert mandados_visibles(admin).count() >= 1          # admin ve todo
    assert mandados_visibles(runner).filter(tarea=t).exists()  # runner ve el suyo
    assert not mandados_visibles(otro).filter(tarea=t).exists()  # ajeno no


def test_vista_lista_y_avanzar(client, proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Mandado
    p = proyecto_factory(estado="en_proceso_diseno")
    admin = usuario_factory(rol="super_admin", email="v@lc.mx")
    t = _tarea(p)
    m = Mandado.objects.get(tarea=t)
    client.force_login(admin)
    assert client.get("/mandados/").status_code == 200
    resp = client.post(f"/mandados/{m.pk}/avanzar", {"accion": "entregado"})
    assert resp.status_code in (302, 200)
    m.refresh_from_db()
    assert m.estado == "entregado"


def test_vista_destino_post(client, proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Mandado
    p = proyecto_factory(estado="en_proceso_diseno")
    admin = usuario_factory(rol="super_admin", email="d@lc.mx")
    t = _tarea(p)
    m = Mandado.objects.get(tarea=t)
    client.force_login(admin)
    resp = client.post(f"/mandados/{m.pk}/destino", {"lat": "19.4", "lng": "-99.1", "etiqueta": "X"})
    assert resp.status_code in (302, 200, 204)
    t.refresh_from_db()
    assert t.destino_lat == 19.4 and t.destino_lng == -99.1
