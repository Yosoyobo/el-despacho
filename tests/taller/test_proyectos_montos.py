"""Tests de plomería de los 4 campos de monto agregados en S2a.2 → S2b prep.

Esto es plomería pura: persistencia + defaults + readback. La lógica de negocio
(qué se considera "pipeline", agregaciones por estado, proyecciones) llega en S2b.
"""

from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_montos_nuevos_defaults_sin_pasar_kwargs(proyecto_factory):
    p = proyecto_factory()
    assert p.monto_cotizado is None
    assert p.monto_facturado == Decimal("0")
    assert p.monto_cobrado == Decimal("0")
    assert p.fecha_ingreso_esperado is None


def test_montos_facturado_y_cobrado_default_decimal_cero_tras_db(proyecto_factory):
    """Tras leer de DB, los defaults llegan como Decimal (no int).

    Django mantiene el int en memoria hasta el primer refresh; este test cubre
    el roundtrip que es lo que importa para agregaciones de SQL en S2b.
    """
    p = proyecto_factory()
    p.refresh_from_db()
    assert isinstance(p.monto_facturado, Decimal)
    assert isinstance(p.monto_cobrado, Decimal)
    assert p.monto_facturado == Decimal("0.00")
    assert p.monto_cobrado == Decimal("0.00")


def test_montos_se_persisten_y_releen(proyecto_factory):
    from apps.los_proyectos.models import Proyecto

    p = proyecto_factory(
        monto_cotizado=Decimal("125000.50"),
        monto_facturado=Decimal("50000.00"),
        monto_cobrado=Decimal("25000.00"),
        fecha_ingreso_esperado=date(2026, 8, 15),
    )
    fresh = Proyecto.objects.get(pk=p.pk)
    assert fresh.monto_cotizado == Decimal("125000.50")
    assert fresh.monto_facturado == Decimal("50000.00")
    assert fresh.monto_cobrado == Decimal("25000.00")
    assert fresh.fecha_ingreso_esperado == date(2026, 8, 15)


def test_facturado_mayor_que_cotizado_es_permitido(proyecto_factory):
    """No hay validador todavía — plomería. La consistencia se valida en S2b."""
    p = proyecto_factory(
        monto_cotizado=Decimal("100.00"),
        monto_facturado=Decimal("150.00"),
    )
    assert p.monto_facturado > p.monto_cotizado


def test_monto_estimado_se_mantiene_intacto(proyecto_factory):
    """Confirmación literal de la regla #5 del sprint: no se tocó monto_estimado."""
    p = proyecto_factory(monto_estimado=Decimal("42000.00"))
    assert p.monto_estimado == Decimal("42000.00")
    assert p.monto_cotizado is None  # los nuevos no lo afectan
