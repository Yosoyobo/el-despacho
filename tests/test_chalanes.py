"""Tests de Los Chalanes v2 — Pre-S2b.1."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lib.analistas.base import ErrorTransitorio, Resultado
from lib.analistas.capacidades import Capability

pytestmark = pytest.mark.django_db


# ── Adapters: apodos y capacidades ──────────────────────────────────────────


def test_chalan_claudio_capacidades():
    from lib.analistas.adapters import AnthropicAdapter
    a = AnthropicAdapter()
    assert a.apodo == "Chalán Claudio"
    assert Capability.VISION in a.capacidades
    assert Capability.TEXTO in a.capacidades


def test_chalan_gpt_capacidades():
    from lib.analistas.adapters import OpenAIAdapter
    a = OpenAIAdapter()
    assert a.apodo == "Chalán GPT"
    assert Capability.VISION in a.capacidades


def test_chalan_chino_sin_vision():
    from lib.analistas.adapters import DeepseekAdapter
    a = DeepseekAdapter()
    assert a.apodo == "Chalán Chino"
    assert Capability.TEXTO in a.capacidades
    assert Capability.VISION not in a.capacidades


def test_gemini_skeleton_no_registrado():
    """Gemini está pero no en _FACTORIES."""
    from lib.analistas import registry
    from lib.analistas.adapters.gemini import GeminiAdapter
    assert "gemini" not in registry._FACTORIES
    assert GeminiAdapter().apodo == "Chalán Gemini"


def test_adapter_legacy_slot_fallback():
    """Anthropic adapter cae al slot legacy si chalan_* no está pero anthropic_api_key sí."""
    from ajustes.models.credencial import Credencial
    from lib.analistas.adapters import AnthropicAdapter
    Credencial.guardar("anthropic_api_key", "sk-ant-legacy")
    a = AnthropicAdapter()
    assert a._llave() == "sk-ant-legacy"


def test_adapter_nuevo_slot_tiene_prioridad():
    from ajustes.models.credencial import Credencial
    from lib.analistas.adapters import AnthropicAdapter
    Credencial.guardar("anthropic_api_key", "viejo")
    Credencial.guardar("chalan_anthropic_api_key", "nuevo")
    assert AnthropicAdapter()._llave() == "nuevo"


# ── Registry DB-aware ───────────────────────────────────────────────────────


def test_registry_apodo():
    from lib.analistas.registry import apodo
    assert apodo("anthropic") == "Chalán Claudio"
    assert apodo("openai") == "Chalán GPT"
    assert apodo("deepseek") == "Chalán Chino"


def test_cadena_usa_cuadro_chalanes():
    from chalanes.models import CuadroChalanes
    from lib.analistas.registry import cadena_de
    # Migration seed: ocr_recibo → openai. Cambiamos a deepseek para test.
    CuadroChalanes.objects.update_or_create(
        estacion="estacion_test", defaults={"proveedor": "deepseek", "modelo": "deepseek-chat"},
    )
    cadena = cadena_de("estacion_test")
    assert cadena[0].nombre == "deepseek"


def test_cadena_respeta_chalan_asignado(usuario_factory):
    from chalanes.models import ChalanAsignado, CuadroChalanes
    from lib.analistas.registry import cadena_de
    u = usuario_factory()
    CuadroChalanes.objects.update_or_create(
        estacion="test_x", defaults={"proveedor": "anthropic", "modelo": "claude"}
    )
    ChalanAsignado.objects.create(usuario=u, estacion="test_x", proveedor="deepseek")
    cadena_sin = cadena_de("test_x", usuario_id=None)
    cadena_con = cadena_de("test_x", usuario_id=u.pk)
    assert cadena_sin[0].nombre == "anthropic"
    assert cadena_con[0].nombre == "deepseek"


def test_cadena_default_sin_cuadro():
    from lib.analistas.registry import cadena_de
    cadena = cadena_de("estacion_inexistente")
    nombres = [a.nombre for a in cadena]
    # Default fallback: anthropic primero (prioridad 1)
    assert "anthropic" in nombres
    assert nombres[0] == "anthropic"


# ── Reemplazo: fallback + log es_fallback ──────────────────────────────────


def test_reemplazo_marca_es_fallback():
    """Anthropic falla, OpenAI responde — log marca es_fallback=True para openai."""
    from ajustes.models.analistas_log import AnalistaLog
    from ajustes.models.credencial import Credencial
    from lib.analistas.adapters import AnthropicAdapter, OpenAIAdapter
    from lib.analistas.reemplazo import analizar

    Credencial.guardar("chalan_anthropic_api_key", "sk-ant-test")
    Credencial.guardar("chalan_openai_api_key", "sk-test")

    def fail(self, prompt, **kw):
        raise ErrorTransitorio("anthropic: 503")

    def ok(self, prompt, **kw):
        return Resultado(
            texto="ok", provider="openai", modelo="gpt-4o-mini",
            prompt_tokens=1, completion_tokens=1, costo_usd=0.0001, latencia_ms=42,
        )

    with patch.object(AnthropicAdapter, "_invocar", fail), \
         patch.object(OpenAIAdapter, "_invocar", ok):
        res = analizar("estacion_falla", "hola")

    assert res.provider == "openai"
    logs = list(AnalistaLog.objects.order_by("creado_en"))
    assert len(logs) == 2
    assert logs[0].provider == "anthropic"
    assert logs[0].exito is False
    assert logs[1].provider == "openai"
    assert logs[1].exito is True
    assert logs[1].es_fallback is True
    assert logs[1].proveedor_original == "anthropic"


def test_reemplazo_salta_sin_credencial():
    """Si fallback no está configurado, se salta — no se loguea intento."""
    from ajustes.models.analistas_log import AnalistaLog
    from ajustes.models.credencial import Credencial
    from lib.analistas.adapters import AnthropicAdapter
    from lib.analistas.reemplazo import TodosFallaron, analizar

    Credencial.guardar("chalan_anthropic_api_key", "sk-ant")
    # openai/deepseek sin credencial

    def fail(self, prompt, **kw):
        raise ErrorTransitorio("anthropic: 503")

    AnalistaLog.objects.all().delete()
    with patch.object(AnthropicAdapter, "_invocar", fail), pytest.raises(TodosFallaron) as exc:
        analizar("estacion_z", "hola")
    nombres = [n for n, _ in exc.value.intentos]
    assert "anthropic" in nombres
    assert "openai" in nombres  # marcado como sin credencial


def test_reemplazo_filtro_capacidad():
    """Si requiere VISION, Chino no entra en la cadena."""
    from ajustes.models.credencial import Credencial
    from lib.analistas.adapters import AnthropicAdapter, OpenAIAdapter
    from lib.analistas.capacidades import Capability
    from lib.analistas.reemplazo import analizar

    Credencial.guardar("chalan_anthropic_api_key", "sk-ant")
    Credencial.guardar("chalan_openai_api_key", "sk")

    def ok(self, prompt, **kw):
        return Resultado(
            texto="ok", provider=self.nombre, modelo=self.modelo,
            prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1,
        )

    with patch.object(AnthropicAdapter, "_invocar", ok), patch.object(OpenAIAdapter, "_invocar", ok):
        res = analizar("estacion_visual", "ver imagen", requiere={Capability.VISION})
    assert res.provider in ("anthropic", "openai")


def test_seed_cuadro_chalanes_existe():
    from chalanes.models import CuadroChalanes
    estaciones = set(CuadroChalanes.objects.values_list("estacion", flat=True))
    assert "cotizaciones" in estaciones
    assert "dictado" in estaciones
    assert "ocr_recibo" in estaciones


def test_seed_cadena_fallback_existe():
    from chalanes.models import CadenaFallback
    cf = list(CadenaFallback.objects.order_by("prioridad").values_list("proveedor", flat=True))
    assert cf[0] == "anthropic"
    assert "openai" in cf
    assert "deepseek" in cf


# ── Slot rename (migración 0004_chalanes_v2) ───────────────────────────────


def test_credencial_slots_chalan_listados():
    from ajustes.models.credencial import SLOTS_CREDENCIAL
    claves = {c for c, _, _ in SLOTS_CREDENCIAL}
    assert "chalan_anthropic_api_key" in claves
    assert "chalan_openai_api_key" in claves
    assert "chalan_deepseek_api_key" in claves
    assert "chalan_gemini_api_key" in claves
    # Legacy se queda hasta limpieza manual
    assert "anthropic_api_key" in claves
    assert "openai_api_key" in claves


# ── UI panel ───────────────────────────────────────────────────────────────


@pytest.fixture
def _urls_gerencia(settings):
    settings.ROOT_URLCONF = "tests.urls_gerencia"


def test_panel_chalanes_solo_admins(client, usuario_factory, _urls_gerencia):
    d = usuario_factory(rol="disenador")
    client.force_login(d)
    r = client.get("/chalanes/")
    assert r.status_code == 403


def test_panel_chalanes_super_admin_ve_secciones(client, usuario_factory, _urls_gerencia):
    a = usuario_factory(rol="super_admin")
    client.force_login(a)
    r = client.get("/chalanes/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "El Cuadro de Chalanes" in body
    assert "La Cadena de Fallback" in body
    assert "Auditoría reciente" in body


def test_guardar_cuadro_emite_evento(client, usuario_factory, _urls_gerencia):
    from chalanes.models import CuadroChalanes
    a = usuario_factory(rol="super_admin")
    client.force_login(a)
    r = client.post("/chalanes/cuadro/guardar", {
        "estacion": "cotizaciones", "proveedor": "deepseek", "modelo": "deepseek-chat",
    })
    assert r.status_code == 302
    fila = CuadroChalanes.objects.get(estacion="cotizaciones")
    assert fila.proveedor == "deepseek"


def test_reordenar_cadena_up(client, usuario_factory, _urls_gerencia):
    from chalanes.models import CadenaFallback
    a = usuario_factory(rol="super_admin")
    client.force_login(a)
    # Seed: anthropic=1, openai=2. Sube openai a posición 1.
    client.post("/chalanes/cadena/reordenar", {"proveedor": "openai", "direccion": "up"})
    p_openai = CadenaFallback.objects.get(proveedor="openai").prioridad
    p_anthropic = CadenaFallback.objects.get(proveedor="anthropic").prioridad
    assert p_openai < p_anthropic
