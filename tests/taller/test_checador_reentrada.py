"""S-LC-Feedback-V11 — re-entrada el mismo día (horas extra) en el Checador.

Decisión Oscar: "aunque cumpla mi jornada del día, si hago más horas de trabajo
cuéntalas, no me haga auto check out. El auto checkout solo aplica cuando la
persona no checa salida antes de las 05:00".
"""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _aware(y, m, d, h, mi=0):
    return timezone.make_aware(datetime.datetime(y, m, d, h, mi))


def test_reentrada_acumula_horas_sin_contar_pausa(usuario_factory):
    """Entrada 9-13 (4h), salida, re-entrada 14-18 (4h) → 8h, NO 9h (la pausa
    13-14 no cuenta)."""
    from apps.checador import services
    u = usuario_factory(rol="disenador")
    services.checar_entrada(u, registrado_en=_aware(2026, 6, 15, 9, 0))
    services.checar_salida(u, registrado_en=_aware(2026, 6, 15, 13, 0))
    # Re-entrada el mismo día.
    j = services.checar_entrada(u, registrado_en=_aware(2026, 6, 15, 14, 0))
    assert j.minutos_extra == 240  # el primer segmento (4h) quedó acumulado
    assert j.salida_en is None and j.estado == "abierta"
    services.checar_salida(u, registrado_en=_aware(2026, 6, 15, 18, 0))
    j.refresh_from_db()
    assert j.minutos_trabajados == 480  # 4h + 4h, sin la pausa
    assert j.horas_trabajadas == 8.0


def test_reentrada_no_recalcula_retardo(usuario_factory):
    """El retardo se fija en la PRIMERA entrada; re-entrar no genera retardo nuevo."""
    from apps.checador import services
    from apps.checador.models import HorarioLaboral
    u = usuario_factory(rol="disenador")
    HorarioLaboral.objects.update_or_create(
        usuario=u, dia_semana=0,  # lunes 2026-06-15
        defaults={"hora_entrada": datetime.time(9, 0), "hora_salida": datetime.time(18, 0),
                  "tolerancia_min": 15, "activo": True},
    )
    services.checar_entrada(u, registrado_en=_aware(2026, 6, 15, 9, 5))  # a tiempo (tolerancia 15)
    services.checar_salida(u, registrado_en=_aware(2026, 6, 15, 13, 0))
    j = services.checar_entrada(u, registrado_en=_aware(2026, 6, 15, 16, 0))  # tardísimo si recalculara
    assert j.retardo_min == 0  # no se recalcula contra el horario en la re-entrada


def test_no_doble_entrada_con_segmento_abierto(usuario_factory):
    """Con un segmento ABIERTO (sin salida) no se puede re-entrar."""
    from apps.checador import services
    u = usuario_factory(rol="disenador")
    services.checar_entrada(u, registrado_en=_aware(2026, 6, 15, 9, 0))
    with pytest.raises(ValueError, match="salida"):
        services.checar_entrada(u, registrado_en=_aware(2026, 6, 15, 10, 0))


def test_auto_cierre_solo_aplica_despues_de_las_5(usuario_factory):
    """El auto check-out NO toca una jornada el mismo día (antes de 05:00 del
    día siguiente); solo cierra pasada esa hora."""
    from apps.checador import services
    from apps.checador.models import Jornada
    u = usuario_factory(rol="disenador")
    services.checar_entrada(u, registrado_en=_aware(2026, 6, 15, 9, 0))
    # Mismo día por la noche: aún NO debe cerrar.
    assert services.cerrar_jornadas_vencidas(ahora=_aware(2026, 6, 15, 23, 0)) == 0
    j = Jornada.objects.get(usuario=u, fecha=datetime.date(2026, 6, 15))
    assert j.salida_en is None
    # Pasadas las 05:00 del día siguiente: cierra automáticamente.
    assert services.cerrar_jornadas_vencidas(ahora=_aware(2026, 6, 16, 5, 10)) == 1
    j.refresh_from_db()
    assert j.salida_en is not None and j.salida_automatica is True
