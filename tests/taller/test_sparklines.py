"""Sparklines 30d en KPI cards financieros."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _ingreso(cliente, autor, *, monto, fecha):
    from apps.tesoreria.models import Ingreso
    return Ingreso.objects.create(
        cliente=cliente, descripcion="x", monto=Decimal(monto),
        fecha=fecha, metodo="efectivo", creado_por=autor,
    )


def _egreso(autor, *, monto, fecha, centro):
    from apps.tesoreria.models import Egreso
    return Egreso.objects.create(
        descripcion="y", monto=Decimal(monto), fecha=fecha,
        metodo="efectivo", centro_de_costo=centro,
        creado_por=autor,
    )


def test_series_30d_largo_y_orden(cliente_factory, usuario_factory):
    from apps.tesoreria.services import series_diarias_30d
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    hoy = date.today()
    _ingreso(cli, autor, monto="100.00", fecha=hoy)
    _ingreso(cli, autor, monto="200.00", fecha=hoy - timedelta(days=5))
    s = series_diarias_30d()
    assert len(s["ingresos"]) == 30
    assert len(s["egresos"]) == 30
    assert len(s["utilidad"]) == 30
    # Último = hoy.
    assert s["ingresos"][-1] == 100.0
    # Día -5 desde el final.
    assert s["ingresos"][-6] == 200.0


def test_series_30d_excluye_fuera_de_ventana(cliente_factory, usuario_factory):
    from apps.tesoreria.services import series_diarias_30d
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    _ingreso(cli, autor, monto="500.00", fecha=date.today() - timedelta(days=45))
    s = series_diarias_30d()
    assert sum(s["ingresos"]) == 0.0


def test_series_30d_utilidad_es_diff(cliente_factory, usuario_factory):
    from apps.tesoreria.models import CentroDeCosto
    from apps.tesoreria.services import series_diarias_30d
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    # Reusa centro existente del seed o crea uno
    centro = CentroDeCosto.objects.first() or CentroDeCosto.objects.create(
        slug="general", nombre="General"
    )
    hoy = date.today()
    _ingreso(cli, autor, monto="1000.00", fecha=hoy)
    _egreso(autor, monto="300.00", fecha=hoy, centro=centro)
    s = series_diarias_30d()
    assert s["utilidad"][-1] == 700.0
