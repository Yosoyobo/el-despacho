"""S-Checador-V1.2 — horas de proyecto como jornada, balance mensual y
auto-cierre de jornadas abiertas."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _aware(y, m, d, h, mi=0):
    return timezone.make_aware(datetime.datetime(y, m, d, h, mi))


def _horario(usuario, dia, ent=(9, 0), sal=(18, 0)):
    from apps.checador.models import HorarioLaboral
    HorarioLaboral.objects.update_or_create(
        usuario=usuario, dia_semana=dia,
        defaults={"hora_entrada": datetime.time(*ent), "hora_salida": datetime.time(*sal),
                  "tolerancia_min": 15, "activo": True},
    )


# ── N3: proyecto cuenta como jornada + filas ──────────────────────────────

def test_filas_semana_proyecto_como_jornada(usuario_factory, proyecto_factory):
    from apps.checador import services
    from apps.checador.models import SesionProyecto
    u = usuario_factory(rol="disenador")
    p = proyecto_factory()
    # Día con SOLO sesión de proyecto (sin jornada) → cuenta como jornada.
    SesionProyecto.objects.create(
        usuario=u, proyecto=p, inicio=_aware(2026, 6, 10, 9, 0),
        fin=_aware(2026, 6, 10, 12, 0), duracion_min=180, estado="cerrada",
    )
    filas = services.filas_semana(u, datetime.date(2026, 6, 8), datetime.date(2026, 6, 14))
    fila = next(f for f in filas if f["fecha"] == datetime.date(2026, 6, 10))
    assert fila["tipo"] == "proyecto"
    assert fila["proyecto_horas"] == 3.0
    assert fila["trabajado_horas"] == 3.0


def test_balance_mensual_deuda(usuario_factory):
    from apps.checador import services
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    for dia in range(5):  # L-V 9-18 (9h)
        _horario(u, dia)
    # Una jornada cerrada de 8h el lunes 8-jun.
    Jornada.objects.create(
        usuario=u, fecha=datetime.date(2026, 6, 8),
        entrada_en=_aware(2026, 6, 8, 9, 0), salida_en=_aware(2026, 6, 8, 17, 0),
        estado="cerrada",
    )
    bal = services.balance_mensual(u, ahora=_aware(2026, 6, 15, 12, 0))
    assert bal["trabajadas_horas"] == 8.0
    assert bal["esperadas_horas"] > 8.0   # muchos días esperados, solo 1 trabajado
    assert bal["balance_horas"] < 0 and bal["a_favor"] is False


# ── N4: auto-cierre de jornadas abiertas ──────────────────────────────────

def test_auto_cierre_jornada_vencida(usuario_factory):
    from apps.checador import services
    from apps.checador.models import HorarioLaboral, Jornada
    u = usuario_factory(rol="disenador")
    # salida default global para el día de la jornada (martes 9-jun-2026 → weekday 1)
    HorarioLaboral.objects.update_or_create(
        usuario=None, dia_semana=1,
        defaults={"hora_entrada": datetime.time(9, 0), "hora_salida": datetime.time(18, 0),
                  "tolerancia_min": 15, "activo": True},
    )
    j = Jornada.objects.create(
        usuario=u, fecha=datetime.date(2026, 6, 9),
        entrada_en=_aware(2026, 6, 9, 9, 30), salida_en=None, estado="abierta",
    )
    # "ahora" = 11-jun 06:00 → ya pasó 05:00 del día siguiente
    n = services.cerrar_jornadas_vencidas(ahora=_aware(2026, 6, 11, 6, 0))
    assert n == 1
    j.refresh_from_db()
    assert j.salida_en == _aware(2026, 6, 9, 18, 0)
    assert j.salida_automatica is True
    assert j.estado == "cerrada"


def test_no_cierra_jornada_de_hoy(usuario_factory):
    from apps.checador import services
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    j = Jornada.objects.create(
        usuario=u, fecha=datetime.date(2026, 6, 11),
        entrada_en=_aware(2026, 6, 11, 9, 30), salida_en=None, estado="abierta",
    )
    # mismo día 18:00 → aún no llega 05:00 del día siguiente
    n = services.cerrar_jornadas_vencidas(ahora=_aware(2026, 6, 11, 18, 0))
    assert n == 0
    j.refresh_from_db()
    assert j.salida_en is None
