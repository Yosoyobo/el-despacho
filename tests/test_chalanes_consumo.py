"""S-Chalanes-Consumo: stats nuevas (kpis_consumo, por_estacion, usuarios_top,
ultimas_llamadas) + filtros de plantilla miles/costo_ia."""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


def _log(actor=None, estacion="dictado", provider="anthropic", pin=100, pout=50,
         costo="0.0010", exito=True):
    from ajustes.models.analistas_log import AnalistaLog
    return AnalistaLog.objects.create(
        estacion=estacion, provider=provider, modelo="m-1",
        prompt_tokens=pin, completion_tokens=pout,
        costo_usd_estimado=Decimal(costo), latencia_ms=10, exito=exito,
        actor=actor,
    )


def test_kpis_consumo(usuario_factory):
    u = usuario_factory(rol="super_admin")
    _log(u, pin=100, pout=50, costo="0.0010")
    _log(u, pin=200, pout=100, costo="0.0020")
    from lib.analistas.stats import kpis_consumo
    k = kpis_consumo(dias=30)
    assert k["llamadas"] == 2
    assert k["tokens_entrada"] == 300
    assert k["tokens_salida"] == 150
    assert k["tokens_total"] == 450
    assert k["costo_total"] == Decimal("0.0030")


def test_por_estacion_agrupa_y_ordena(usuario_factory):
    u = usuario_factory(rol="super_admin")
    _log(u, estacion="dictado", costo="0.0010")
    _log(u, estacion="ocr_recibo", costo="0.0050")
    from lib.analistas.stats import estadisticas_por_estacion
    filas = estadisticas_por_estacion(dias=30)
    assert filas[0]["estacion"] == "ocr_recibo"  # mayor costo primero
    assert {f["estacion"] for f in filas} == {"dictado", "ocr_recibo"}
    assert filas[0]["porcentaje_costo"] == 100.0


def test_usuarios_top(usuario_factory):
    a = usuario_factory(rol="super_admin")
    b = usuario_factory(rol="disenador")
    for _ in range(3):
        _log(a)
    _log(b)
    from lib.analistas.stats import usuarios_top
    top = usuarios_top(dias=30, limit=10)
    assert top[0]["actor_id"] == a.pk
    assert top[0]["llamadas"] == 3


def test_ultimas_llamadas(usuario_factory):
    u = usuario_factory(rol="super_admin")
    _log(u, estacion="dictado")
    from lib.analistas.stats import ultimas_llamadas
    filas = ultimas_llamadas(dias=30, limit=50)
    assert len(filas) == 1
    assert filas[0]["actor_email"] == u.email
    assert filas[0]["provider"] == "anthropic"


def test_filtros_miles_y_costo():
    from cuentas.templatetags.forms_helpers import costo_ia, miles
    assert miles(55582) == "55,582"
    assert miles(0) == "0"
    assert costo_ia(Decimal("0.0365")) == "$0.0365"
    assert costo_ia(Decimal("0.0001")) == "< $0.001"
    assert costo_ia(None) == "—"
