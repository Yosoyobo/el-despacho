"""La voz editable se inyecta en los builders de prompt de las estaciones.

Verifica que el Prompt base + voz por estación lleguen al prompt final que
se manda al Chalán, sin tocar el contenido estructural.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _cache_limpio():
    from chalanes.voz import invalidar_cache_voz
    invalidar_cache_voz()
    yield
    invalidar_cache_voz()


def test_chat_system_prompt_inyecta_voz(usuario_factory):
    from apps.el_dictado.prompt_chat import construir_system_prompt

    from chalanes.models import PromptVoz
    from chalanes.voz import invalidar_cache_voz
    PromptVoz.objects.filter(clave="taller_chat").update(contenido="VOZCHAT_XYZ")
    invalidar_cache_voz()
    u = usuario_factory(rol="super_admin")
    sp = construir_system_prompt(u)
    assert "VOZCHAT_XYZ" in sp
    # El contenido estructural (alcance estricto) sigue presente.
    assert "ALCANCE ESTRICTO" in sp


def test_dictado_inyecta_voz_en_prompt(monkeypatch, usuario_factory):
    from chalanes.models import PromptVoz
    from chalanes.voz import invalidar_cache_voz
    PromptVoz.objects.filter(clave="base").update(contenido="VOZBASE_DICT")
    invalidar_cache_voz()

    capturado = {}

    class _Res:
        provider = "anthropic"
        modelo = "x"
        texto = '{"acciones": []}'
        latencia_ms = 1
        costo_usd = 0

    def fake_analizar(*, estacion, prompt, **kw):  # noqa: ARG001
        capturado["prompt"] = prompt
        return _Res()

    import lib.analistas as la
    monkeypatch.setattr(la, "analizar", fake_analizar)

    from apps.el_dictado import services
    u = usuario_factory(rol="super_admin")
    services.interpretar(texto="cambia el estado del proyecto", usuario=u)
    assert "VOZBASE_DICT" in capturado["prompt"]
    # El esquema estructural (tipos de acción) sigue presente.
    assert "TIPOS DE ACCIÓN" in capturado["prompt"]
