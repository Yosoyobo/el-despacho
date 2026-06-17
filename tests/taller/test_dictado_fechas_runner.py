"""Regresiones de los ejecutores del Dictado vistas en prod (El Chalán multi-paso):

- crear_tarea/crear_mandado crasheaban cuando el LLM metía la hora en
  `fecha_compromiso` ('2026-06-18T15:00:00') siendo DateField.
- asignar_runner no resolvía `@accion_N` → "Field 'id' expected a number".
"""

from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# ── _fecha_hora_de ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("payload,esperado", [
    ({"fecha_compromiso": "2026-06-18T15:00:00"}, ("2026-06-18", "15:00:00")),
    ({"fecha_compromiso": "2026-06-18 15:00"}, ("2026-06-18", "15:00")),
    ({"fecha_compromiso": "2026-06-18", "hora": "09:30"}, ("2026-06-18", "09:30")),
    ({"fecha_compromiso": "2026-06-18"}, ("2026-06-18", None)),
    ({}, (None, None)),
])
def test_fecha_hora_de(payload, esperado):
    from apps.el_dictado.ejecutores.basicos import _fecha_hora_de
    assert _fecha_hora_de(payload) == esperado


# ── crear_tarea: hora dentro de fecha_compromiso ────────────────────────────────

def test_crear_tarea_separa_fecha_y_hora(usuario_factory, proyecto_factory):
    from apps.el_dictado.ejecutores import basicos
    from apps.el_pizarron.models import Tarea
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    acc = SimpleNamespace(payload={
        "proyecto_slug": p.slug, "titulo": "Entregar players",
        "fecha_compromiso": "2026-06-18T15:00:00",  # el LLM metió la hora aquí
    })
    basicos.crear_tarea(acc, u, {"entidades_creadas": {}})
    t = Tarea.objects.get(pk=acc.entidad_id)
    assert t.fecha_compromiso == date(2026, 6, 18)
    assert t.hora == time(15, 0)


# ── _resolver_tarea: @accion_N + numérico ───────────────────────────────────────

def test_resolver_tarea_por_referencia_y_pk(usuario_factory, proyecto_factory):
    from apps.el_dictado.ejecutores.basicos import _resolver_tarea
    from apps.el_pizarron.models import Tarea
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="X")
    ctx = {"entidades_creadas": {0: {"tipo": "tarea", "id": t.pk}}}
    assert _resolver_tarea("@accion_0", ctx).pk == t.pk     # referencia entre acciones
    assert _resolver_tarea(str(t.pk), ctx).pk == t.pk        # pk numérico
    with pytest.raises(ValueError):
        _resolver_tarea("@accion_9", ctx)                    # referencia inexistente


# ── cadena completa vía aplicar: crear_tarea(entrega) → asignar_runner @accion_0 ──

def test_cadena_crear_tarea_entrega_y_asignar_runner(usuario_factory, proyecto_factory):
    from apps.el_dictado.models import Dictado, DictadoAccion
    from apps.el_dictado.services import aplicar
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    d = Dictado.objects.create(autor=u, texto_crudo="(chat)", origen="taller_chat",
                               estado="esperando_confirmacion")
    DictadoAccion.objects.create(dictado=d, orden=0, tipo="crear_tarea", descripcion="entrega",
                                 payload={"proyecto_slug": p.slug, "titulo": "Entregar players",
                                          "tipo": "entrega", "fecha_compromiso": "2026-06-18T15:00:00"},
                                 confirmada=True)
    DictadoAccion.objects.create(dictado=d, orden=1, tipo="asignar_runner", descripcion="runner",
                                 payload={"tarea_id": "@accion_0"}, confirmada=True)
    aplicar(dictado=d, usuario=u)
    a0 = d.acciones.get(orden=0)
    a1 = d.acciones.get(orden=1)
    # La tarea (con datetime) se crea OK ahora.
    assert a0.aplicada is True
    # El runner ya NO crashea por el id: la referencia @accion_0 se resuelve.
    err = a1.error_al_aplicar or ""
    assert "expected a number" not in err
    assert "@accion" not in err
