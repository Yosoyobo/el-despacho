"""Fix de referencias @/#/$ en el chat de El Chalán (2026-06-08).

Bug B: el chat mandaba el mensaje crudo al LLM; ahora resuelve los tokens
(`@usuario/#proyecto/$cliente`) a entidades reales y los inyecta como bloque
[REFERENCIAS RESUELTAS] para que el modelo sepa el código/nombre exactos.
(Bug A — Enter del autocomplete — es JS en referencias.js, se valida manual.)
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_bloque_referencias_resuelve_proyecto(usuario_factory, cliente_factory):
    from apps.el_dictado.services_chat import _bloque_referencias
    from apps.los_proyectos.models import Proyecto
    actor = usuario_factory(rol="dueno")
    cliente = cliente_factory()
    p = Proyecto.objects.create(nombre="EXTE", cliente=cliente, creado_por=actor)
    bloque = _bloque_referencias(f"dame el status de #{p.slug}")
    assert "REFERENCIAS" in bloque
    assert p.codigo in bloque
    assert "EXTE" in bloque
    assert p.slug in bloque


def test_bloque_referencias_no_encontrado():
    from apps.el_dictado.services_chat import _bloque_referencias
    bloque = _bloque_referencias("status de #fantasma-inexistente-xyz")
    assert "(no encontrado)" in bloque


def test_bloque_referencias_sin_tokens_vacio():
    from apps.el_dictado.services_chat import _bloque_referencias
    assert _bloque_referencias("cuántos proyectos activos hay") == ""


def test_conversar_inyecta_referencias_en_prompt(monkeypatch, usuario_factory, cliente_factory):
    from apps.el_dictado import services_chat
    from apps.los_proyectos.models import Proyecto

    import lib.analistas as la
    actor = usuario_factory(rol="dueno")
    cliente = cliente_factory()
    p = Proyecto.objects.create(nombre="EXTE", cliente=cliente, creado_por=actor)
    conv = services_chat.crear_conversacion(usuario=actor)

    capturado = {}

    def fake(estacion, prompt, **kw):
        capturado["prompt"] = prompt
        return SimpleNamespace(texto=json.dumps({"tipo": "responder", "texto": "ok"}), provider="anthropic")

    monkeypatch.setattr(la, "analizar", fake)
    services_chat.conversar(mensaje=f"dame el status de #{p.slug}", usuario=actor, conversacion=conv)
    assert "REFERENCIAS RESUELTAS" in capturado["prompt"]
    assert p.codigo in capturado["prompt"]


def test_bloque_prompt_compartido_es_el_mismo(usuario_factory, cliente_factory):
    """El chat delega en la fuente única `referencias.bloque.bloque_prompt`."""
    from apps.el_dictado.services_chat import _bloque_referencias
    from apps.los_proyectos.models import Proyecto

    from referencias.bloque import bloque_prompt
    actor = usuario_factory(rol="dueno")
    p = Proyecto.objects.create(nombre="EXTE", cliente=cliente_factory(), creado_por=actor)
    texto = f"status de #{p.slug}"
    assert _bloque_referencias(texto) == bloque_prompt(texto)
    assert p.codigo in bloque_prompt(texto)


def _mock_resultado(texto_json: str):
    from lib.analistas.base import Resultado
    return Resultado(
        texto=texto_json, provider="anthropic", modelo="claude-opus-4-7",
        prompt_tokens=100, completion_tokens=200, costo_usd=0.001, latencia_ms=50,
    )


def test_interpretar_estandar_inyecta_referencias(usuario_factory, cliente_factory):
    """El Dictado estándar (no solo el chat) resuelve los `#proyecto` para el LLM."""
    from unittest.mock import patch

    from apps.el_dictado.services import interpretar
    from apps.los_proyectos.models import Proyecto
    actor = usuario_factory(rol="dueno")
    p = Proyecto.objects.create(nombre="EXTE", cliente=cliente_factory(), creado_por=actor)

    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(json.dumps({"pregunta_clarificacion": None, "acciones": []}))
        interpretar(texto=f"dame el status de #{p.slug}", usuario=actor)
    prompt = mock.call_args.kwargs["prompt"]
    assert "REFERENCIAS RESUELTAS" in prompt
    assert p.codigo in prompt


def test_interpretar_resuelve_referencia_de_clarificacion(usuario_factory, cliente_factory):
    """Un `#proyecto` mencionado en una respuesta de clarificación se resuelve."""
    from unittest.mock import patch

    from apps.el_dictado.models import Dictado
    from apps.el_dictado.services import interpretar
    from apps.los_proyectos.models import Proyecto
    actor = usuario_factory(rol="dueno")
    p = Proyecto.objects.create(nombre="EXTE", cliente=cliente_factory(), creado_por=actor)
    dictado = Dictado.objects.create(
        autor=actor, texto_crudo="cobra a ese proyecto", estado="preguntando",
        historial_clarificaciones=[{"pregunta": "¿cuál proyecto?", "respuesta": f"el #{p.slug}"}],
    )

    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(json.dumps({"pregunta_clarificacion": None, "acciones": []}))
        interpretar(dictado=dictado, usuario=actor)
    prompt = mock.call_args.kwargs["prompt"]
    assert p.codigo in prompt
