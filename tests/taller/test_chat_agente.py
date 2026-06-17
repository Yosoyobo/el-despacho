"""Tests del loop AGENTE del Chat del Taller — tool-use nativo + El Relevo.

Mockean `lib.analistas.chatear` con `Resultado`s canned (tool_calls / texto) y
fuerzan el modo nativo via `_cadena_soporta_tools`. No pegan a ningún LLM.
"""

from __future__ import annotations

import pytest

from lib.analistas.base import Resultado, ToolCall

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _res(texto="", tool_calls=()):
    return Resultado(
        texto=texto, provider="anthropic", modelo="claude-haiku-4-5",
        prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1,
        tool_calls=tuple(tool_calls), stop_reason="tool_use" if tool_calls else "end",
    )


def _fake_chatear(secuencia):
    """Fake de `chatear` que emite `secuencia` en orden y registra estaciones."""
    estado = {"i": 0, "estaciones": []}

    def fake(estacion, mensajes, **kw):
        estado["estaciones"].append(estacion)
        i = estado["i"]
        estado["i"] += 1
        return secuencia[i] if i < len(secuencia) else secuencia[-1]

    return fake, estado


def _conv(usuario):
    from apps.el_dictado.services_chat import crear_conversacion
    return crear_conversacion(usuario=usuario)


def _forzar_nativo(monkeypatch):
    from apps.el_dictado import services_chat
    monkeypatch.setattr(services_chat, "_cadena_soporta_tools", lambda u: True)


# ── Modo nativo ───────────────────────────────────────────────────────────────

def test_nativo_responde_directo(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    _forzar_nativo(monkeypatch)
    u = usuario_factory(rol="super_admin")
    fake, estado = _fake_chatear([_res("Hay 5 proyectos activos.")])
    monkeypatch.setattr(la, "chatear", fake)

    res = conversar(mensaje="¿cuántos proyectos?", usuario=u, conversacion=_conv(u))
    assert estado["i"] == 1
    tipos = [(m.rol, m.tipo) for m in res["mensajes"]]
    assert tipos == [("user", "texto"), ("bot", "texto")]
    assert "5 proyectos" in res["mensajes"][-1].cuerpo


def test_nativo_herramienta_y_responde(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    _forzar_nativo(monkeypatch)
    u = usuario_factory(rol="super_admin")
    fake, estado = _fake_chatear([
        _res(tool_calls=[ToolCall("c1", "gasto_ia", {"dias": 30})]),
        _res("Llevas poco gasto en IA."),
    ])
    monkeypatch.setattr(la, "chatear", fake)

    res = conversar(mensaje="¿cuánto gasto en IA?", usuario=u, conversacion=_conv(u))
    assert estado["i"] == 2
    tipos = [(m.rol, m.tipo) for m in res["mensajes"]]
    assert tipos == [("user", "texto"), ("bot", "herramienta"), ("bot", "texto")]


def test_nativo_proponer_acciones_crea_dictado(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import TOOL_PROPONER, conversar

    import lib.analistas as la
    _forzar_nativo(monkeypatch)
    u = usuario_factory(rol="super_admin")
    fake, _ = _fake_chatear([_res(tool_calls=[ToolCall("c1", TOOL_PROPONER, {
        "texto": "Te propongo esto",
        "acciones": [{"tipo": "crear_recado", "descripcion": "Recado a Ana",
                      "payload": {"destinatarios_slugs": [], "cuerpo": "hola"}, "confianza": 0.9}],
    })])])
    monkeypatch.setattr(la, "chatear", fake)

    res = conversar(mensaje="mándale un recado a @ana", usuario=u, conversacion=_conv(u))
    dictado = res["dictado"]
    assert dictado is not None
    assert dictado.acciones.count() == 1
    assert res["mensajes"][-1].tipo == "accion"


def test_nativo_proponer_filtra_prohibidos(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import TOOL_PROPONER, conversar

    import lib.analistas as la
    _forzar_nativo(monkeypatch)
    u = usuario_factory(rol="super_admin")
    fake, _ = _fake_chatear([_res(tool_calls=[ToolCall("c1", TOOL_PROPONER, {
        "acciones": [{"tipo": "modificar_ajustes", "descripcion": "cambiar llave", "payload": {}}],
    })])])
    monkeypatch.setattr(la, "chatear", fake)

    res = conversar(mensaje="cambia la llave de anthropic", usuario=u, conversacion=_conv(u))
    # La acción prohibida se filtra → 0 acciones → NO deja dictado fantasma:
    # responde con texto en vez de una tarjeta de acción vacía.
    assert res["dictado"] is None
    assert res["mensajes"][-1].tipo == "texto"


def test_relevo_escala_a_modelo_profundo(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import TOOL_ESCALAR, conversar

    import lib.analistas as la
    _forzar_nativo(monkeypatch)
    u = usuario_factory(rol="super_admin")
    fake, estado = _fake_chatear([
        _res(tool_calls=[ToolCall("c1", TOOL_ESCALAR, {"motivo": "hay que analizar"})]),
        _res("Análisis listo."),
    ])
    monkeypatch.setattr(la, "chatear", fake)

    res = conversar(mensaje="necesito ayuda", usuario=u, conversacion=_conv(u))
    # Pre-ruteo rápido, luego El Relevo escala a la estación profunda.
    assert estado["estaciones"] == ["taller_chat", "taller_chat_profundo"]
    tipos = [(m.rol, m.tipo, m.nombre_herramienta) for m in res["mensajes"]]
    assert ("bot", "herramienta", "relevo") in tipos
    assert res["mensajes"][-1].cuerpo == "Análisis listo."


def test_relevo_preruteo_profundo_por_pregunta_analitica(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    _forzar_nativo(monkeypatch)
    u = usuario_factory(rol="super_admin")
    fake, estado = _fake_chatear([_res("Listo.")])
    monkeypatch.setattr(la, "chatear", fake)

    conversar(mensaje="analiza la rentabilidad y recomiéndame qué priorizar",
              usuario=u, conversacion=_conv(u))
    assert estado["estaciones"][0] == "taller_chat_profundo"


def test_degrada_a_texto_cuando_no_hay_function_calling(monkeypatch, usuario_factory):
    """Sin Chalán con FUNCTION_CALLING configurado, usa el path de texto
    (sobre-JSON) — NO llama `chatear`."""
    import json as _json

    from apps.el_dictado import services_chat
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    monkeypatch.setattr(services_chat, "_cadena_soporta_tools", lambda u: False)
    u = usuario_factory(rol="super_admin")

    def _chatear_no(*a, **k):
        raise AssertionError("no debe llamar chatear en modo degradado")

    monkeypatch.setattr(la, "chatear", _chatear_no)

    def fake_analizar(estacion, prompt, **kw):
        from types import SimpleNamespace
        return SimpleNamespace(
            texto=_json.dumps({"tipo": "responder", "texto": "Hola desde texto."}),
            provider="anthropic", modelo="claude-haiku-4-5",
            prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1,
        )

    monkeypatch.setattr(la, "analizar", fake_analizar)
    res = conversar(mensaje="hola", usuario=u, conversacion=_conv(u))
    assert res["mensajes"][-1].cuerpo == "Hola desde texto."


# ── Bug fix: propone pero no aplica (acciones sin tipo válido) ─────────────────

def test_schema_proponer_constrine_tipo_a_enum(usuario_factory):
    from apps.el_dictado.services_chat import _schema_proponer
    u = usuario_factory(rol="super_admin")
    enum = _schema_proponer(u)["properties"]["acciones"]["items"]["properties"]["tipo"]["enum"]
    assert "crear_mandado" in enum and "crear_tarea" in enum


def test_proponer_sin_tipo_valido_no_deja_dictado_fantasma(monkeypatch, usuario_factory):
    """Si el modelo propone una acción sin `tipo` válido, se filtra → 0 acciones.
    No debe quedar una tarjeta de acción que al aplicar dé 0/0 (el bug); el bot
    responde con un texto pidiendo más detalle y no devuelve dictado."""
    from apps.el_dictado.services_chat import TOOL_PROPONER, conversar

    import lib.analistas as la
    _forzar_nativo(monkeypatch)
    u = usuario_factory(rol="super_admin")
    fake, _ = _fake_chatear([_res(tool_calls=[ToolCall("c1", TOOL_PROPONER, {
        "texto": "Propongo crear un mandado de entrega",
        "acciones": [{"descripcion": "entrega de playeras", "payload": {}}],  # SIN tipo
    })])])
    monkeypatch.setattr(la, "chatear", fake)

    res = conversar(mensaje="llevar playeras a Noko mañana", usuario=u, conversacion=_conv(u))
    assert res["dictado"] is None
    assert res["mensajes"][-1].tipo == "texto"
    assert "No pude estructurar" in res["mensajes"][-1].cuerpo
