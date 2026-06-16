"""S-Chalan-Equipo-UX — El Chalán opera El Checador.

El Chalán puede registrar jornada, tiempo de proyecto y visitas, y pedir
ajustes de jornada, en nombre del usuario que dicta. Gating por permiso
`checador.checar` (defensa en profundidad) + happy-path de cada ejecutor.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def _on_commit_inmediato(monkeypatch):
    """Bug E §14: fuerza transaction.on_commit a correr dentro del rollback."""
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _accion(payload):
    return SimpleNamespace(payload=payload, entidad_tipo=None, entidad_id=None)


def _revocar_checar(usuario):
    from cuentas.models.permiso_usuario import PermisoUsuario
    PermisoUsuario.objects.update_or_create(
        usuario=usuario, modulo="checador", permiso="checar",
        defaults={"activo": False},
    )


# ── Registro ───────────────────────────────────────────────────────────────────

def test_ejecutores_registrados():
    from apps.el_dictado.ejecutores import EJECUTORES
    esperados = {
        "checador_iniciar_jornada", "checador_cerrar_jornada",
        "checador_registrar_tiempo_proyecto", "checador_iniciar_tiempo_proyecto",
        "checador_detener_tiempo_proyecto", "checador_registrar_visita",
        "checador_solicitar_ajuste_jornada",
    }
    assert esperados <= set(EJECUTORES)


def test_comandos_para_incluye_checador(usuario_factory):
    from lib.dictado_catalogo import comandos_para
    u = usuario_factory(rol="disenador")  # todo el staff puede checar por default
    tipos = {c["tipo"] for c in comandos_para(u)}
    assert "checador_registrar_tiempo_proyecto" in tipos
    assert "checador_registrar_visita" in tipos


def test_comandos_para_excluye_si_revocado(usuario_factory):
    from lib.dictado_catalogo import comandos_para
    u = usuario_factory(rol="disenador")
    _revocar_checar(u)
    tipos = {c["tipo"] for c in comandos_para(u)}
    assert "checador_registrar_tiempo_proyecto" not in tipos
    assert "crear_tarea" in tipos  # las abiertas siguen (crear_proyecto ahora es admin)


# ── Gating (defensa en profundidad) ────────────────────────────────────────────

def test_registrar_visita_rechaza_sin_permiso(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    _revocar_checar(u)
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["checador_registrar_visita"](_accion({"tipo": "otro"}), u, {})


# ── Happy path ──────────────────────────────────────────────────────────────────

def test_iniciar_jornada(usuario_factory, _on_commit_inmediato):
    from apps.checador.models import Jornada
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    accion = _accion({})
    EJECUTORES["checador_iniciar_jornada"](accion, u, {})
    assert accion.entidad_tipo == "jornada"
    j = Jornada.objects.get(pk=accion.entidad_id)
    assert j.usuario_id == u.pk
    assert j.entrada_en is not None
    assert j.entrada_sin_geo  # el Chalán no captura GPS


def test_registrar_tiempo_proyecto(usuario_factory, proyecto_factory, _on_commit_inmediato):
    from apps.checador.models import SesionProyecto
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    p = proyecto_factory()
    accion = _accion({
        "proyecto_slug": p.slug, "hora_inicio": "10:00", "hora_fin": "12:30",
        "nota": "Diseño",
    })
    EJECUTORES["checador_registrar_tiempo_proyecto"](accion, u, {})
    assert accion.entidad_tipo == "sesion_proyecto"
    s = SesionProyecto.objects.get(pk=accion.entidad_id)
    assert s.usuario_id == u.pk
    assert s.duracion_min == 150


def test_registrar_tiempo_proyecto_fin_antes_inicio(usuario_factory, proyecto_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    p = proyecto_factory()
    with pytest.raises(ValueError):
        EJECUTORES["checador_registrar_tiempo_proyecto"](
            _accion({"proyecto_slug": p.slug, "hora_inicio": "12:00", "hora_fin": "10:00"}), u, {}
        )


def test_registrar_visita_cliente(usuario_factory, cliente_factory, _on_commit_inmediato):
    from apps.checador.models import Visita
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    cli = cliente_factory()
    accion = _accion({"cliente_slug": cli.slug, "nota": "Entrega"})
    EJECUTORES["checador_registrar_visita"](accion, u, {})
    assert accion.entidad_tipo == "visita"
    v = Visita.objects.get(pk=accion.entidad_id)
    assert v.tipo == "cliente"
    assert v.cliente_id == cli.pk
    assert v.sin_geo


def test_solicitar_ajuste_jornada(usuario_factory, _on_commit_inmediato):
    from apps.checador.models import SolicitudCorreccion
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    accion = _accion({
        "fecha": "2026-06-10", "hora_entrada": "09:00", "hora_salida": "18:00",
        "motivo": "Olvidé checar",
    })
    EJECUTORES["checador_solicitar_ajuste_jornada"](accion, u, {})
    assert accion.entidad_tipo == "solicitud_correccion"
    sol = SolicitudCorreccion.objects.get(pk=accion.entidad_id)
    assert sol.usuario_id == u.pk
    assert sol.estado == "pendiente"


def test_solicitar_ajuste_sin_horas_falla(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    with pytest.raises(ValueError, match="hora_entrada|hora_salida"):
        EJECUTORES["checador_solicitar_ajuste_jornada"](
            _accion({"fecha": "2026-06-10", "motivo": "x"}), u, {}
        )


# ── Herramientas read-only del chat ─────────────────────────────────────────────

def test_herramienta_mi_jornada_hoy(usuario_factory):
    from apps.el_dictado.herramientas import ejecutar_herramienta
    u = usuario_factory(rol="disenador")
    out = ejecutar_herramienta("mi_jornada_hoy", {}, u)
    assert out.get("estado") == "sin_checar"


def test_herramienta_mis_horas_semana(usuario_factory):
    from apps.el_dictado.herramientas import ejecutar_herramienta
    u = usuario_factory(rol="disenador")
    out = ejecutar_herramienta("mis_horas_semana", {}, u)
    assert "jornada_horas" in out
