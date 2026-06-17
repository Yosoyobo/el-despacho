"""S-LC-Proyecto-V2 (Oscar): El Runner — entregas/recolecciones delegadas.

Auto-asignación (menos cargado), asignación manual, El Chalán asigna, y el
runner ve la tarea en SUS pendientes.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _tarea(proyecto, **kw):
    from apps.el_pizarron.models import Tarea
    defaults = dict(titulo="Entregar lona", tipo="entrega", estado="pendiente")
    defaults.update(kw)
    return Tarea.objects.create(proyecto=proyecto, **defaults)


def _hacer_runner(*usuarios):
    """S-Roles-V2: runner es opt-in vía el rol "Runner" (sembrado en cuentas/0033)."""
    from cuentas.models.rol import Rol
    r = Rol.objects.get(nombre="Runner")
    for u in usuarios:
        u.roles_extra.add(r)


def test_auto_asigna_menos_cargado(proyecto_factory, usuario_factory):
    from apps.el_pizarron import runners
    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="a@lc.mx")
    b = usuario_factory(rol="disenador", email="b@lc.mx")
    _hacer_runner(a, b)
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
    _hacer_runner(usuario_factory(rol="disenador", email="run@lc.mx"))  # candidato elegible
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
    _hacer_runner(usuario_factory(rol="disenador", email="run2@lc.mx"))
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


def test_form_runner_dropdown_lista_a_todos(usuario_factory):
    """Bug Oscar 2026-06-17: la asignación MANUAL puede caer en cualquier usuario
    activo, tenga o no el rol Runner. El permiso solo gobierna la auto-asignación,
    así que el <select> lista a todos (incluido quien no es runner)."""
    from apps.el_pizarron.forms import TareaForm
    elegible = usuario_factory(rol="disenador", email="elig@lc.mx")
    no_runner = usuario_factory(rol="disenador", email="norun@lc.mx")
    _hacer_runner(elegible)  # solo este es runner elegible
    qs = TareaForm().fields["runner"].queryset
    assert elegible in qs
    assert no_runner in qs  # ← ahora SÍ aparece para asignación manual


def test_form_runner_dropdown_no_vacio_sin_runners(usuario_factory):
    """Sin nadie con el rol Runner el dropdown SIGUE listando a todos (para
    asignar a mano), pero la auto-asignación no tiene a quién elegir."""
    from apps.el_pizarron import runners
    from apps.el_pizarron.forms import TareaForm
    a = usuario_factory(rol="disenador", email="x1@lc.mx")
    b = usuario_factory(rol="super_admin", email="x2@lc.mx")
    qs = TareaForm().fields["runner"].queryset
    assert a in qs and b in qs
    assert runners.usuarios_runner() == []  # auto no tiene candidato


def test_aplicar_desde_form_runner_manual_no_elegible(proyecto_factory, usuario_factory):
    """Asignar a mano a alguien SIN permiso de runner debe funcionar (Bug 3)."""
    from apps.el_pizarron import runners
    p = proyecto_factory(estado="en_proceso_diseno")
    no_runner = usuario_factory(rol="disenador", email="manual@lc.mx")
    t = _tarea(p)  # tipo entrega
    runners.aplicar_desde_form(t, {"runner": no_runner, "runner_auto": False})
    t.refresh_from_db()
    assert t.runner_id == no_runner.pk
    assert t.runner_auto is False
    assert no_runner not in runners.usuarios_runner()  # no elegible para auto


def test_aplicar_desde_form_idempotente_no_repickea(proyecto_factory, usuario_factory):
    """Reaplicar el form sin cambios no reasigna (evita re-push en cada edición)."""
    from apps.el_pizarron import runners
    p = proyecto_factory(estado="en_proceso_diseno")
    manual = usuario_factory(rol="disenador", email="fijo@lc.mx")
    t = _tarea(p, runner=manual, runner_auto=False, requiere_runner=True)
    antes = t.runner_asignado_en
    runners.aplicar_desde_form(t, {"runner": manual, "runner_auto": False})
    t.refresh_from_db()
    assert t.runner_id == manual.pk
    assert t.runner_asignado_en == antes  # no se reasignó


def test_editar_tarea_guarda_runner(client, proyecto_factory, usuario_factory):
    """Bug 1: editar la tarea aplica el runner elegido (antes form.save() lo
    descartaba porque no está en Meta.fields)."""
    p = proyecto_factory(estado="en_proceso_diseno")
    admin = usuario_factory(rol="super_admin", email="ed@lc.mx")
    runner = usuario_factory(rol="disenador", email="elegido@lc.mx")
    t = _tarea(p, asignada_a=admin, fecha_compromiso=date(2026, 6, 18))
    client.force_login(admin)
    resp = client.post(reverse("pizarron-editar-tarea", args=[t.pk]), {
        "titulo": t.titulo, "descripcion": "", "estado": t.estado,
        "prioridad": "media", "tipo": "entrega",
        "asignada_a": admin.pk, "fecha_compromiso": "2026-06-18",
        "runner": runner.pk,  # runner_auto NO enviado ⇒ False
    })
    assert resp.status_code == 302
    t.refresh_from_db()
    assert t.runner_id == runner.pk
    assert t.runner_auto is False
    assert t.fecha_compromiso == date(2026, 6, 18)


def test_form_fecha_compromiso_render_iso(proyecto_factory, usuario_factory):
    """Bug 2: al editar, la fecha guardada se rendea como ISO (YYYY-MM-DD) para
    que `<input type=date>` la muestre, en vez de quedar en blanco."""
    from apps.el_pizarron.forms import TareaForm
    p = proyecto_factory(estado="en_proceso_diseno")
    admin = usuario_factory(rol="super_admin", email="iso@lc.mx")
    t = _tarea(p, asignada_a=admin, fecha_compromiso=date(2026, 6, 18))
    html = str(TareaForm(instance=t)["fecha_compromiso"])
    assert 'value="2026-06-18"' in html


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
