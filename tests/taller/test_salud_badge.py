"""Fase 7 (LC 2026-07) — badge ⚠️ de salud del sistema."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_sin_chequeos_no_hay_falla():
    from lib.salud_sistema import hay_falla
    r = hay_falla(usar_cache=False)
    assert r["falla"] is False


def test_integracion_en_error_enciende_falla():
    from lib.salud_sistema import hay_falla
    from lib.site import almacen
    almacen.guardar("anthropic", "error", mensaje_error="401")
    r = hay_falla(usar_cache=False)
    assert r["falla"] is True
    assert "anthropic" in r["motivo"]


def test_ultimo_ok_no_falla():
    from lib.salud_sistema import hay_falla
    from lib.site import almacen
    almacen.guardar("openai", "error")
    almacen.guardar("openai", "ok")  # el ÚLTIMO manda
    r = hay_falla(usar_cache=False)
    assert r["falla"] is False
