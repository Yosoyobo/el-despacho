"""S-Checador E1 — cimientos: services, seed de horario, permisos."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

# 2026-06-08 es lunes → cae en el horario global default (L-V 9:00-18:00).
LUNES = datetime.date(2026, 6, 8)


def _dt(hora, minuto, fecha=LUNES):
    """Datetime aware en hora local de México."""
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(hora, minuto)))


# ───────────────────────── seed + horario ─────────────────────────

def test_seed_horario_global_lunes_a_viernes():
    from apps.checador.models import HorarioLaboral
    globales = HorarioLaboral.objects.filter(usuario__isnull=True, activo=True)
    assert globales.count() == 5
    assert set(globales.values_list("dia_semana", flat=True)) == {0, 1, 2, 3, 4}
    lunes = globales.get(dia_semana=0)
    assert lunes.hora_entrada == datetime.time(9, 0)
    assert lunes.tolerancia_min == 15


def test_horario_vigente_override_gana_sobre_global(usuario_factory):
    from apps.checador import services
    from apps.checador.models import HorarioLaboral
    u = usuario_factory()
    HorarioLaboral.objects.create(
        usuario=u, dia_semana=0, hora_entrada=datetime.time(11, 0),
        hora_salida=datetime.time(20, 0), tolerancia_min=10,
    )
    h = services.horario_vigente(u, LUNES)
    assert h.usuario_id == u.pk
    assert h.hora_entrada == datetime.time(11, 0)


# ───────────────────────── jornada ─────────────────────────

def test_checar_entrada_a_tiempo_sin_retardo(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    jornada = services.checar_entrada(u, geo={"lat": 19.4, "lng": -99.1, "precision": 12}, registrado_en=_dt(9, 5))
    assert jornada.estado == "abierta"
    assert jornada.retardo_min == 0
    assert jornada.entrada_sin_geo is False
    assert jornada.entrada_lat == 19.4


def test_checar_entrada_tarde_calcula_retardo(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    # 9:40, tolerancia 15 → 40 - 15 = 25 min de retardo.
    jornada = services.checar_entrada(u, registrado_en=_dt(9, 40))
    assert jornada.retardo_min == 25


def test_checar_entrada_sin_geo(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    jornada = services.checar_entrada(u, geo=None, registrado_en=_dt(9, 0))
    assert jornada.entrada_sin_geo is True
    assert jornada.entrada_lat is None


def test_checar_entrada_idempotente_por_uuid(usuario_factory):
    from apps.checador import services
    from apps.checador.models import Jornada
    u = usuario_factory()
    services.checar_entrada(u, registrado_en=_dt(9, 0), uuid="abc-123")
    services.checar_entrada(u, registrado_en=_dt(9, 30), uuid="abc-123")
    assert Jornada.objects.filter(usuario=u).count() == 1


def test_checar_entrada_doble_sin_uuid_falla(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    services.checar_entrada(u, registrado_en=_dt(9, 0))
    with pytest.raises(ValueError, match="entrada"):
        services.checar_entrada(u, registrado_en=_dt(9, 30))


def test_checar_salida_cierra_jornada(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    services.checar_entrada(u, registrado_en=_dt(9, 0))
    jornada = services.checar_salida(u, registrado_en=_dt(18, 0))
    assert jornada.estado == "cerrada"
    assert jornada.minutos_trabajados == 9 * 60


def test_checar_salida_sin_entrada_falla(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    with pytest.raises(ValueError, match="entrada"):
        services.checar_salida(u, registrado_en=_dt(18, 0))


# ───────────────────────── visitas ─────────────────────────

def test_registrar_visita_cliente_requiere_cliente(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    with pytest.raises(ValueError, match="cliente"):
        services.registrar_visita(u, tipo="cliente", registrado_en=_dt(11, 0))


def test_registrar_visita_cliente_limpia_proveedor(usuario_factory, cliente_factory):
    from apps.checador import services
    from apps.el_catalogo.models import Proveedor
    u = usuario_factory()
    cliente = cliente_factory()
    prov = Proveedor.objects.create(razon_social="Prov X")
    v = services.registrar_visita(u, tipo="cliente", cliente=cliente, proveedor=prov, registrado_en=_dt(11, 0))
    assert v.cliente_id == cliente.pk
    assert v.proveedor_id is None


def test_registrar_visita_idempotente_por_uuid(usuario_factory, cliente_factory):
    from apps.checador import services
    from apps.checador.models import Visita
    u = usuario_factory()
    cliente = cliente_factory()
    services.registrar_visita(u, tipo="cliente", cliente=cliente, registrado_en=_dt(11, 0), uuid="v-1")
    services.registrar_visita(u, tipo="cliente", cliente=cliente, registrado_en=_dt(12, 0), uuid="v-1")
    assert Visita.objects.filter(usuario=u).count() == 1


# ───────────────────────── timer ─────────────────────────

def test_iniciar_timer_cierra_el_activo_previo(usuario_factory, proyecto_factory):
    from apps.checador import services
    from apps.checador.models import SesionProyecto
    u = usuario_factory()
    p1 = proyecto_factory()
    p2 = proyecto_factory()
    services.iniciar_timer(u, p1, inicio=_dt(10, 0))
    services.iniciar_timer(u, p2, inicio=_dt(11, 0))
    activas = SesionProyecto.objects.filter(usuario=u, estado="activa")
    assert activas.count() == 1
    assert activas.first().proyecto_id == p2.pk
    cerrada = SesionProyecto.objects.get(usuario=u, proyecto=p1)
    assert cerrada.estado == "cerrada"
    assert cerrada.duracion_min == 60


def test_detener_timer_sin_activo_falla(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    with pytest.raises(ValueError, match="cronómetro"):
        services.detener_timer(u)


def test_capturar_sesion_manual_fin_antes_de_inicio_falla(usuario_factory, proyecto_factory):
    from apps.checador import services
    u = usuario_factory()
    p = proyecto_factory()
    with pytest.raises(ValueError, match="posterior"):
        services.capturar_sesion_manual(u, p, inicio=_dt(12, 0), fin=_dt(11, 0))


def test_capturar_sesion_manual_calcula_duracion(usuario_factory, proyecto_factory):
    from apps.checador import services
    u = usuario_factory()
    p = proyecto_factory()
    s = services.capturar_sesion_manual(u, p, inicio=_dt(10, 0), fin=_dt(12, 30))
    assert s.estado == "cerrada"
    assert s.duracion_min == 150
    assert s.origen == "manual"


# ───────────────────────── correcciones ─────────────────────────

def test_resolver_correccion_aprobada_aplica_y_recalcula(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    jornada = services.checar_entrada(u, registrado_en=_dt(9, 40))  # retardo 25
    assert jornada.retardo_min == 25
    sol = services.solicitar_correccion(
        u, tipo="entrada", valor_propuesto=_dt(9, 5), motivo="Marqué tarde por error",
        jornada=jornada,
    )
    admin = usuario_factory(rol="super_admin")
    services.resolver_correccion(sol, admin=admin, aprobar=True, comentario="ok")
    jornada.refresh_from_db()
    assert jornada.entrada_en == _dt(9, 5)
    assert jornada.retardo_min == 0


def test_resolver_correccion_rechazada_no_aplica(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    jornada = services.checar_entrada(u, registrado_en=_dt(9, 40))
    sol = services.solicitar_correccion(
        u, tipo="entrada", valor_propuesto=_dt(9, 5), motivo="x", jornada=jornada,
    )
    admin = usuario_factory(rol="super_admin")
    services.resolver_correccion(sol, admin=admin, aprobar=False, comentario="no procede")
    jornada.refresh_from_db()
    assert jornada.retardo_min == 25  # sin cambios


def test_resolver_correccion_ya_resuelta_falla(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    jornada = services.checar_entrada(u, registrado_en=_dt(9, 40))
    sol = services.solicitar_correccion(u, tipo="entrada", valor_propuesto=_dt(9, 5), motivo="x", jornada=jornada)
    admin = usuario_factory(rol="super_admin")
    services.resolver_correccion(sol, admin=admin, aprobar=True)
    with pytest.raises(ValueError, match="resuelta"):
        services.resolver_correccion(sol, admin=admin, aprobar=True)


# ───────────────────────── agregados + permisos ─────────────────────────

def test_horas_de_agrega_jornada_y_sesiones(usuario_factory, proyecto_factory):
    from apps.checador import services
    u = usuario_factory()
    services.checar_entrada(u, registrado_en=_dt(9, 0))
    services.checar_salida(u, registrado_en=_dt(17, 0))  # 8 h
    services.capturar_sesion_manual(u, proyecto_factory(), inicio=_dt(10, 0), fin=_dt(12, 0))  # 2 h
    agg = services.horas_de(u, LUNES, LUNES)
    assert agg["dias"] == 1
    assert agg["jornada_horas"] == 8.0
    assert agg["sesiones_horas"] == 2.0


def test_permisos_disenador_checa_pero_no_ve_equipo(usuario_factory):
    from lib.permisos import puede_checar, puede_ver_equipo_checador
    u = usuario_factory(rol="disenador")
    assert puede_checar(u) is True
    assert puede_ver_equipo_checador(u) is False


def test_permisos_super_admin_todo(usuario_factory):
    from lib.permisos import (
        puede_aprobar_correcciones_checador,
        puede_configurar_horarios_checador,
        puede_exportar_checador,
        puede_ver_equipo_checador,
    )
    u = usuario_factory(rol="super_admin")
    assert puede_ver_equipo_checador(u)
    assert puede_aprobar_correcciones_checador(u)
    assert puede_configurar_horarios_checador(u)
    assert puede_exportar_checador(u)
