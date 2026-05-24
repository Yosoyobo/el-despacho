"""Override de costo_usd para proveedores gratis (S-Demo-Pre-Showcase #1).

Cubre el bug del $0.0033 histórico de MiMo: logs viejos con
`costo_usd_estimado > 0` no inflan los totales del panel ni del Site
una vez que el adapter pasa a PRECIO_IN+PRECIO_OUT == 0.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def _log_mimo_caro():
    """Persiste un AnalistaLog histórico de MiMo con costo > 0
    (simulando registros previos a que MiMo pasara a gratis)."""
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


def test_mimo_costo_se_neutraliza(_log_mimo_caro):
    from lib.analistas.stats import estadisticas_proveedores
    stats = estadisticas_proveedores(dias=30)
    assert "mimo" in stats
    # Tokens y llamadas se preservan (no se pierde la actividad).
    assert stats["mimo"]["tokens"] == 1500
    assert stats["mimo"]["llamadas"] == 1
    # Pero el costo se neutraliza a 0 porque PRECIO_IN+OUT == 0.
    assert stats["mimo"]["costo_usd"] == Decimal("0.000000")


def test_anthropic_costo_se_preserva(_log_anthropic):
    from lib.analistas.stats import estadisticas_proveedores
    stats = estadisticas_proveedores(dias=30)
    assert "anthropic" in stats
    assert stats["anthropic"]["costo_usd"] == Decimal("0.005700")


def test_resumen_global_excluye_mimo_del_costo(_log_mimo_caro, _log_anthropic):
    from lib.analistas.stats import resumen_global
    res = resumen_global(dias=30)
    # MiMo sigue en llamadas/tokens, pero no en costo_total.
    assert res["llamadas_total"] == 2
    assert res["tokens_total"] == 2250
    assert res["costo_total"] == Decimal("0.005700")
    # En la lista por_proveedor, MiMo aparece con es_gratis=True y costo 0.
    mimo_entry = next(p for p in res["por_proveedor"] if p["provider"] == "mimo")
    assert mimo_entry["es_gratis"] is True
    assert mimo_entry["costo_usd"] == Decimal("0.000000")


def test_tarjetas_chalanes_mimo_es_gratis():
    from lib.analistas.stats import tarjetas_chalanes
    tarjetas = tarjetas_chalanes(dias=30)
    mimo = next((t for t in tarjetas if t["nombre"] == "mimo"), None)
    assert mimo is not None
    assert mimo["es_gratis"] is True
