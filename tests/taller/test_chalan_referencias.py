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
