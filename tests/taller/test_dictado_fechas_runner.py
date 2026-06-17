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

@pytest.mark.parametrize("tipo_in,payload_in,esperado_tipo,esperado_subtipo", [
    ("entrega", {"cliente_slug": "x"}, "crear_mandado", "entrega"),
    ("recoger", {}, "crear_mandado", "recoger"),
    ("envío", {}, "crear_mandado", "entrega"),
    ("tarea", {}, "crear_tarea", "tarea"),
    ("junta", {}, "crear_tarea", "junta"),
])
def test_normalizar_accion_alias(tipo_in, payload_in, esperado_tipo, esperado_subtipo):
    from apps.el_dictado.services import _normalizar_accion
    tipo, payload = _normalizar_accion(tipo_in, payload_in)
    assert tipo == esperado_tipo
    assert payload["tipo"] == esperado_subtipo


def test_normalizar_accion_sin_alias_no_toca():
    from apps.el_dictado.services import _normalizar_accion
    assert _normalizar_accion("crear_tarea", {"x": 1}) == ("crear_tarea", {"x": 1})


def test_chat_persiste_entrega_como_mandado(usuario_factory, cliente_factory, proyecto_factory):
    """tipo='entrega' (que el LLM usó como acción) → se persiste como crear_mandado
    y se aplica creando la entrega para el proyecto activo del cliente."""
    from apps.el_dictado.services import aplicar
    from apps.el_dictado.services_chat import _persistir_acciones_chat
    from apps.el_pizarron.models import Tarea
    u = usuario_factory(rol="super_admin")
    c = cliente_factory()
    p = proyecto_factory(cliente=c, estado="en_proceso_produccion")
    d = _persistir_acciones_chat(
        acciones_raw=[{"tipo": "entrega", "descripcion": "Entregar players",
                       "payload": {"cliente_slug": c.slug, "titulo": "Entregar players",
                                   "fecha_compromiso": "2026-06-18", "hora": "15:00"}}],
        usuario=u, chalan="openai",
    )
    a = d.acciones.get(orden=0)
    assert a.tipo == "crear_mandado"
    a.confirmada = True
    a.save(update_fields=["confirmada"])
    aplicar(dictado=d, usuario=u)
    a.refresh_from_db()
    assert a.aplicada is True
    t = Tarea.objects.get(pk=a.entidad_id)
    assert t.proyecto_id == p.pk and t.tipo == "entrega"


def test_resolver_proyecto_por_cliente_unico(cliente_factory, proyecto_factory):
    """'entregar para $cliente' sin proyecto → usa el único proyecto activo."""
    from apps.el_dictado.ejecutores.basicos import _resolver_proyecto_para
    c = cliente_factory()
    p = proyecto_factory(cliente=c, estado="en_proceso_diseno")
    assert _resolver_proyecto_para({"cliente_slug": c.slug}, {}).pk == p.pk


def test_resolver_proyecto_cliente_varios_pide_cual(cliente_factory, proyecto_factory):
    from apps.el_dictado.ejecutores.basicos import _resolver_proyecto_para
    c = cliente_factory()
    proyecto_factory(cliente=c, estado="en_proceso_diseno")
    proyecto_factory(cliente=c, estado="por_cotizar")
    with pytest.raises(ValueError, match="varios proyectos"):
        _resolver_proyecto_para({"cliente_slug": c.slug}, {})


def test_resolver_proyecto_cliente_sin_proyectos(cliente_factory):
    from apps.el_dictado.ejecutores.basicos import _resolver_proyecto_para
    c = cliente_factory()
    with pytest.raises(ValueError, match="no tiene proyectos activos"):
        _resolver_proyecto_para({"cliente_slug": c.slug}, {})


def test_crear_mandado_por_cliente(usuario_factory, cliente_factory, proyecto_factory):
    from apps.el_dictado.ejecutores import basicos
    from apps.el_pizarron.models import Tarea
    u = usuario_factory(rol="super_admin")
    c = cliente_factory()
    p = proyecto_factory(cliente=c, estado="en_proceso_produccion")
    acc = SimpleNamespace(payload={
        "cliente_slug": c.slug, "titulo": "Entregar players", "tipo": "entrega",
        "fecha_compromiso": "2026-06-18", "hora": "15:00",
    })
    basicos.crear_mandado(acc, u, {"entidades_creadas": {}})
    t = Tarea.objects.get(pk=acc.entidad_id)
    assert t.proyecto_id == p.pk and t.tipo == "entrega" and t.hora == time(15, 0)


def test_chat_dictado_no_reinterpreta_y_preserva_error(usuario_factory, cliente_factory):
    """Fix 2: un dictado del chat con acción fallida NO se re-interpreta (que
    borraría el error y daría fallo_ia mudo). El error concreto se preserva."""
    from apps.el_dictado.models import Dictado, DictadoAccion
    from apps.el_dictado.services import aplicar
    u = usuario_factory(rol="super_admin")
    c = cliente_factory()  # cliente SIN proyectos activos
    d = Dictado.objects.create(autor=u, texto_crudo="(chat)", origen="taller_chat",
                               estado="esperando_confirmacion")
    DictadoAccion.objects.create(dictado=d, orden=0, tipo="crear_mandado", descripcion="entrega",
                                 payload={"cliente_slug": c.slug, "titulo": "Entregar players",
                                          "tipo": "entrega"}, confirmada=True)
    res = aplicar(dictado=d, usuario=u)
    assert res["aplicadas"] == 0 and res["fallidas"] == 1
    assert d.acciones.count() == 1  # NO se borró por re-interpret
    assert "no tiene proyectos activos" in d.acciones.get(orden=0).error_al_aplicar


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
