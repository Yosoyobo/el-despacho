"""lib.site.almacen — wrapper sobre site_chequeo."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_guardar_inserta_fila():
    from apps.el_site.models import SiteChequeo

    from lib.site.almacen import guardar
    row = guardar("anthropic", "ok", latencia_ms=150, origen="manual", actor_email="x@y.com")
    assert row.pk is not None
    assert SiteChequeo.objects.count() == 1
    assert SiteChequeo.objects.first().plataforma == "anthropic"


@pytest.mark.django_db
def test_ultimo_por_plataforma_sin_datos():
    from lib.site.almacen import ultimo_por_plataforma
    from lib.site.registry import PLATAFORMAS
    r = ultimo_por_plataforma()
    assert set(r.keys()) == set(PLATAFORMAS.keys())
    for _plat, info in r.items():
        assert info["estado"] == "sin_datos"
        assert info["probado_en"] is None


@pytest.mark.django_db
def test_ultimo_por_plataforma_con_datos():
    from lib.site.almacen import guardar, ultimo_por_plataforma
    guardar("anthropic", "ok", latencia_ms=200, origen="diario")
    guardar("anthropic", "error", mensaje_error="boom", origen="manual", actor_email="x@y.com")
    r = ultimo_por_plataforma()
    # El más reciente es el de error
    assert r["anthropic"]["estado"] == "error"
    assert r["anthropic"]["mensaje_error"] == "boom"


@pytest.mark.django_db
def test_hay_integraciones_rojas():
    from lib.site.almacen import guardar, hay_integraciones_rojas
    assert hay_integraciones_rojas() == 0
    guardar("anthropic", "ok", origen="diario")
    guardar("openai", "error", mensaje_error="x", origen="diario")
    assert hay_integraciones_rojas() == 1
    guardar("postgres", "error", origen="diario")
    assert hay_integraciones_rojas() == 2


@pytest.mark.django_db
def test_guardar_trunca_mensaje_largo():
    from lib.site.almacen import guardar
    msg = "x" * 5000
    row = guardar("openai", "error", mensaje_error=msg, origen="diario")
    assert row.mensaje_error is not None
    assert len(row.mensaje_error) <= 1000
