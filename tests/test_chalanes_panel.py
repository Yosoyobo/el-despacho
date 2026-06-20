"""S-Chalanes-Panel: auto-add a CadenaFallback, stats, probar, borrar llave."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from django.utils import timezone


@pytest.mark.django_db
def test_signal_auto_agrega_chalan_nuevo_a_cadena():
    from ajustes.models.credencial import Credencial
    from chalanes.models import CadenaFallback

    # Estado inicial: prio max del seed = 3 (anthropic/openai/deepseek) + mimo seedeada por 0003 = 4.
    inicial = CadenaFallback.objects.filter(proveedor="mimo").exists()
    assert inicial, "data migration 0003_seed_mimo_cadena debió sembrar mimo"

    # Limpia mimo y vuelve a guardar credencial → signal recrea.
    CadenaFallback.objects.filter(proveedor="mimo").delete()
    assert not CadenaFallback.objects.filter(proveedor="mimo").exists()

    Credencial.guardar("chalan_mimo_api_key", "mimo-test-key-xxx")
    assert CadenaFallback.objects.filter(proveedor="mimo").exists()


@pytest.mark.django_db
def test_signal_ignora_proveedor_desconocido():
    from ajustes.models.credencial import Credencial
    from chalanes.models import CadenaFallback

    Credencial.guardar("chalan_inventado_api_key", "x" * 30)
    assert not CadenaFallback.objects.filter(proveedor="inventado").exists()


@pytest.mark.django_db
def test_signal_no_duplica_si_ya_existe():
    from ajustes.models.credencial import Credencial
    from chalanes.models import CadenaFallback

    n0 = CadenaFallback.objects.filter(proveedor="mimo").count()
    Credencial.guardar("chalan_mimo_api_key", "x" * 30)
    Credencial.guardar("chalan_mimo_api_key", "y" * 30)
    assert CadenaFallback.objects.filter(proveedor="mimo").count() == n0


@pytest.mark.django_db
def test_estadisticas_proveedores_agrega_por_provider():
    from ajustes.models.analistas_log import AnalistaLog
    from lib.analistas.stats import estadisticas_proveedores

    for prov, ok, costo, pt, ct in [
        ("openai", True, "0.0010", 100, 50),
        ("openai", True, "0.0005", 50, 25),
        ("openai", False, "0.0000", 0, 0),
        ("mimo", True, "0.0002", 20, 10),
    ]:
        AnalistaLog.objects.create(
            estacion="recetas", provider=prov, modelo="x",
            prompt_hash="h", prompt_tokens=pt, completion_tokens=ct,
            costo_usd_estimado=Decimal(costo), exito=ok,
        )
    stats = estadisticas_proveedores(dias=30)
    assert stats["openai"]["llamadas"] == 3
    assert stats["openai"]["llamadas_falla"] == 1
    assert stats["openai"]["llamadas_ok"] == 2
    assert stats["openai"]["tokens"] == 225
    assert stats["openai"]["costo_usd"] == Decimal("0.001500")
    assert stats["mimo"]["llamadas"] == 1


@pytest.mark.django_db
def test_estadisticas_excluye_fuera_de_ventana():
    from ajustes.models.analistas_log import AnalistaLog
    from lib.analistas.stats import estadisticas_proveedores

    log = AnalistaLog.objects.create(
        estacion="recetas", provider="openai", modelo="x",
        prompt_hash="h", prompt_tokens=10, completion_tokens=5,
        costo_usd_estimado=Decimal("0.001"), exito=True,
    )
    AnalistaLog.objects.filter(pk=log.pk).update(creado_en=timezone.now() - timedelta(days=60))
    stats = estadisticas_proveedores(dias=30)
    assert "openai" not in stats


@pytest.mark.django_db
def test_tarjetas_incluye_todos_los_chalanes_registrados():
    from lib.analistas.registry import _FACTORIES
    from lib.analistas.stats import tarjetas_chalanes
    tarjetas = tarjetas_chalanes(dias=30)
    nombres = {t["nombre"] for t in tarjetas}
    # Incluye los 5 cloud + ollama (Chalán Llama, Test).
    assert nombres == set(_FACTORIES)
    assert {"anthropic", "openai", "deepseek", "mimo", "gemini", "ollama"} <= nombres


@pytest.mark.django_db
def test_tarjeta_enmascara_llave():
    from ajustes.models.credencial import Credencial
    from lib.analistas.stats import tarjetas_chalanes
    Credencial.guardar("chalan_mimo_api_key", "sk-szv4n3w4n1hb031t9p31yroal68m32djtaj6zuv011cj3kf7")
    tarjetas = tarjetas_chalanes(dias=30)
    mimo = next(t for t in tarjetas if t["nombre"] == "mimo")
    assert mimo["configurado"] is True
    assert mimo["llave_enmascarada"].startswith("sk-s")
    assert mimo["llave_enmascarada"].endswith("3kf7")
    assert "••••" in mimo["llave_enmascarada"]


@pytest.mark.django_db
def test_adapter_probar_sin_credencial_devuelve_no_configurada():
    from lib.analistas.adapters.mimo import MimoAdapter
    res = MimoAdapter().probar()
    assert res["ok"] is False
    assert res["estado"] == "no_configurada"


@pytest.mark.django_db
def test_adapter_probar_ok_persiste_resultado_via_view():
    from ajustes.models.credencial import Credencial
    from cuentas.models.usuario import Usuario

    Credencial.guardar("chalan_mimo_api_key", "mimo-key-xxx")
    user = Usuario.objects.create_user(
        email="root@bautista.mx", password="x", rol="super_admin", nombre_completo="Root",
    )

    class _RespOk:
        status_code = 200
        text = ""
        def json(self):
            return {
                "model": "mimo-v2.5-pro",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    client = Client()
    client.force_login(user)
    with override_settings(ROOT_URLCONF="tests.urls_gerencia"), \
         patch("httpx.post", return_value=_RespOk()):
        resp = client.post("/chalanes/mimo/probar")
    assert resp.status_code == 302  # redirect a panel
    cred = Credencial.objects.get(clave="chalan_mimo_api_key")
    assert cred.ultimo_test_ok is True
    assert cred.ultimo_test_en is not None


@pytest.mark.django_db
def test_borrar_llave_elimina_credencial():
    from ajustes.models.credencial import Credencial
    from cuentas.models.usuario import Usuario

    Credencial.guardar("chalan_mimo_api_key", "x" * 30)
    user = Usuario.objects.create_user(
        email="root2@bautista.mx", password="x", rol="super_admin", nombre_completo="Root",
    )
    client = Client()
    client.force_login(user)
    with override_settings(ROOT_URLCONF="tests.urls_gerencia"):
        resp = client.post("/chalanes/mimo/borrar-llave")
    assert resp.status_code == 302
    assert not Credencial.objects.filter(clave="chalan_mimo_api_key").exists()


# ── S-Chalan-Agente fix: Chalán sin llave sale del relevo/cadena ──────────────

@pytest.mark.django_db
def test_borrar_llave_desactiva_en_cadena():
    """Al borrar la credencial, el proveedor se desactiva en la CadenaFallback
    (no se elimina la fila) y al re-pegar la llave se reactiva."""
    from ajustes.models.credencial import Credencial
    from chalanes.models import CadenaFallback

    Credencial.guardar("chalan_mimo_api_key", "x" * 30)  # post_save → fila activa
    fila = CadenaFallback.objects.get(proveedor="mimo")
    assert fila.activo

    Credencial.objects.filter(clave="chalan_mimo_api_key").delete()  # post_delete
    fila.refresh_from_db()
    assert fila.activo is False  # desactivada, no borrada
    assert CadenaFallback.objects.filter(proveedor="mimo").exists()

    Credencial.guardar("chalan_mimo_api_key", "y" * 30)  # re-pegar → reactiva
    fila.refresh_from_db()
    assert fila.activo is True


@pytest.mark.django_db
def test_analizar_salta_primario_sin_llave_sin_loguear():
    """El primario SIN credencial se salta en silencio (no se intenta ni se
    loguea en rojo): El Relevo usa el siguiente Chalán configurado."""
    from unittest.mock import patch

    from ajustes.models.analistas_log import AnalistaLog
    from ajustes.models.credencial import Credencial
    from chalanes.models import CuadroChalanes
    from lib.analistas.adapters import AnthropicAdapter
    from lib.analistas.base import Resultado
    from lib.analistas.reemplazo import analizar

    Credencial.guardar("chalan_anthropic_api_key", "sk-ant")  # configurado (entra al fallback)
    CuadroChalanes.objects.update_or_create(
        estacion="estacion_w",
        defaults={"proveedor": "gemini", "modelo": "gemini-2.5-flash"},  # primario SIN llave
    )
    AnalistaLog.objects.all().delete()

    def ok(self, prompt, **kw):  # noqa: ARG001
        return Resultado(texto="hola", provider="anthropic", modelo="x",
                         prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1)

    with patch.object(AnthropicAdapter, "_invocar", ok):
        res = analizar("estacion_w", "hola")
    assert res.provider == "anthropic"  # saltó gemini sin llave y usó el configurado
    assert not AnalistaLog.objects.filter(provider="gemini").exists()  # no ensucia la auditoría
