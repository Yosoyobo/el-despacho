"""S-LC-Proyecto-V2 (Oscar): El Runner — entregas/recolecciones delegadas.

Auto-asignación (menos cargado), asignación manual, El Chalán asigna, y el
runner ve la tarea en SUS pendientes.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _tarea(proyecto, **kw):
    from apps.el_pizarron.models import Tarea
    defaults = dict(titulo="Entregar lona", tipo="entrega", estado="pendiente")
    defaults.update(kw)
    return Tarea.objects.create(proyecto=proyecto, **defaults)


def test_auto_asigna_menos_cargado(proyecto_factory, usuario_factory):
    from apps.el_pizarron import runners
    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="a@lc.mx")
    b = usuario_factory(rol="disenador", email="b@lc.mx")
    # Ana ya carga 2 entregas abiertas → nunca debe ser la elegida (el sistema
    # toma a alguien con 0 pendientes, desempatado por pk).
    _tarea(p, runner=a)
    _tarea(p, runner=a)
    t = _tarea(p)
    elegido = runners.asignar_runner_auto(t)
    assert elegido != a
    assert runners.pendientes_runner(elegido) <= 1  # solo la recién asignada
    t.refresh_from_db()
    assert t.runner_id == elegido.pk
    assert t.runner_auto is True
    assert t.requiere_runner is True
    # Beto (0 carga, elegible) está en el universo de candidatos.
    assert b in runners.usuarios_runner()


def test_asignar_manual(proyecto_factory, usuario_factory):
    from apps.el_pizarron import runners
    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="m@lc.mx")
    t = _tarea(p)
    runners.asignar_runner(t, a)
    t.refresh_from_db()
    assert t.runner_id == a.pk
    assert t.runner_auto is False


def test_aplicar_desde_form_noop_en_tarea_normal(proyecto_factory):
    from apps.el_pizarron import runners
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p, tipo="tarea")
    runners.aplicar_desde_form(t, {"runner": None, "runner_auto": True})
    t.refresh_from_db()
    assert t.runner_id is None
    assert t.requiere_runner is False


def test_ejecutor_crear_tarea_entrega_auto(proyecto_factory, usuario_factory):
    """El Chalán crea una entrega sin runner explícito → el sistema lo asigna."""
    from apps.el_dictado.ejecutores.basicos import crear_tarea
    p = proyecto_factory(estado="en_proceso_diseno")
    actor = usuario_factory(rol="super_admin", email="jefe@lc.mx")
    usuario_factory(rol="disenador", email="run@lc.mx")  # candidato elegible
    accion = SimpleNamespace(
        payload={"proyecto_slug": p.slug, "titulo": "Llevar caja", "tipo": "entrega"},
        entidad_tipo=None, entidad_id=None,
    )
    crear_tarea(accion, actor)
    from apps.el_pizarron.models import Tarea
    t = Tarea.objects.get(pk=accion.entidad_id)
    assert t.tipo == "entrega"
    assert t.requiere_runner is True
    assert t.runner_id is not None  # auto-asignado entre los elegibles


def test_ejecutor_asignar_runner_auto(proyecto_factory, usuario_factory):
    from apps.el_dictado.ejecutores.basicos import asignar_runner_ejec
    p = proyecto_factory(estado="en_proceso_diseno")
    actor = usuario_factory(rol="super_admin", email="jefe2@lc.mx")
    usuario_factory(rol="disenador", email="run2@lc.mx")
    t = _tarea(p)
    accion = SimpleNamespace(payload={"tarea_id": t.pk}, entidad_tipo=None, entidad_id=None)
    asignar_runner_ejec(accion, actor)
    t.refresh_from_db()
    assert t.runner_id is not None


def test_ejecutor_asignar_runner_rechaza_tarea_normal(proyecto_factory, usuario_factory):
    from apps.el_dictado.ejecutores.basicos import asignar_runner_ejec
    p = proyecto_factory(estado="en_proceso_diseno")
    actor = usuario_factory(rol="super_admin", email="jefe3@lc.mx")
    t = _tarea(p, tipo="tarea")
    accion = SimpleNamespace(payload={"tarea_id": t.pk}, entidad_tipo=None, entidad_id=None)
    with pytest.raises(ValueError):
        asignar_runner_ejec(accion, actor)


def test_form_runner_dropdown_solo_elegibles(usuario_factory):
    """El <select> de runner del TareaForm solo lista usuarios con el permiso
    (runner, recibir). Revocar el permiso a alguien lo saca del dropdown."""
    from apps.el_pizarron.forms import TareaForm
    from cuentas.models.permiso_usuario import PermisoUsuario
    elegible = usuario_factory(rol="disenador", email="elig@lc.mx")
    no_runner = usuario_factory(rol="disenador", email="norun@lc.mx")
    # Override individual: revoca (runner, recibir) — gana sobre el default del rol.
    PermisoUsuario.objects.update_or_create(
        usuario=no_runner, modulo="runner", permiso="recibir",
        defaults={"activo": False},
    )
    qs = TareaForm().fields["runner"].queryset
    assert elegible in qs
    assert no_runner not in qs


def test_runner_ve_en_sus_pendientes(proyecto_factory, usuario_factory):
    from apps.el_dictado.herramientas import _h_mis_tareas
    from apps.taller_home.views import _mis_tareas
    p = proyecto_factory(estado="en_proceso_diseno")
    runner = usuario_factory(rol="disenador", email="ve@lc.mx")
    _tarea(p, runner=runner, titulo="Mi entrega")
    lista, total = _mis_tareas(runner)
    assert total >= 1
    assert any(t.titulo == "Mi entrega" for t in lista)
    out = _h_mis_tareas({}, runner)
    assert any(f["titulo"] == "Mi entrega" for f in out["tareas"])
