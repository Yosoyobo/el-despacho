"""Stats de IA: todos los proveedores cuentan su costo real.

S-Chalan-Chat-V1: MiMo dejó de ser gratis. Se eliminó el override `_es_gratis`
y la clave `es_gratis` — el costo se toma directo de `costo_usd_estimado`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def _log_mimo():
    from ajustes.models.analistas_log import AnalistaLog
    return AnalistaLog.objects.create(
        estacion="dictado", provider="mimo", modelo="mimo-v2.5-pro",
        prompt_hash="hash1", exito=True,
        prompt_tokens=1000, completion_tokens=500,
        costo_usd_estimado=Decimal("0.0033"),
        latencia_ms=120,
    )


@pytest.fixture
def _log_anthropic():
    from ajustes.models.analistas_log import AnalistaLog
    return AnalistaLog.objects.create(
        estacion="dictado", provider="anthropic", modelo="claude-opus-4-7",
        prompt_hash="hash2", exito=True,
        prompt_tokens=500, completion_tokens=250,
        costo_usd_estimado=Decimal("0.0057"),
        latencia_ms=200,
    )


def test_mimo_costo_se_cuenta(_log_mimo):
    from lib.analistas.stats import estadisticas_proveedores
    stats = estadisticas_proveedores(dias=30)
    assert "mimo" in stats
    assert stats["mimo"]["tokens"] == 1500
    assert stats["mimo"]["llamadas"] == 1
    # Ya no se neutraliza: cuenta el costo real del log.
    assert stats["mimo"]["costo_usd"] == Decimal("0.003300")


def test_anthropic_costo_se_preserva(_log_anthropic):
    from lib.analistas.stats import estadisticas_proveedores
    stats = estadisticas_proveedores(dias=30)
    assert "anthropic" in stats
    assert stats["anthropic"]["costo_usd"] == Decimal("0.005700")


def test_resumen_global_suma_todos(_log_mimo, _log_anthropic):
    from lib.analistas.stats import resumen_global
    res = resumen_global(dias=30)
    assert res["llamadas_total"] == 2
    assert res["tokens_total"] == 2250
    # MiMo ahora SÍ cuenta en el costo total.
    assert res["costo_total"] == Decimal("0.009000")
    mimo_entry = next(p for p in res["por_proveedor"] if p["provider"] == "mimo")
    assert "es_gratis" not in mimo_entry
    assert mimo_entry["costo_usd"] == Decimal("0.003300")


def test_tarjetas_chalanes_sin_es_gratis():
    from lib.analistas.stats import tarjetas_chalanes
    tarjetas = tarjetas_chalanes(dias=30)
    mimo = next((t for t in tarjetas if t["nombre"] == "mimo"), None)
    assert mimo is not None
    assert "es_gratis" not in mimo
