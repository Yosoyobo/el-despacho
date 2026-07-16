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


def test_nativo_propuesta_por_accion_crea_dictado(monkeypatch, usuario_factory):
    """El Chalán propone llamando el tool de la acción (crear_recado); se bufferea
    y al cerrar el turno se materializa como UN Dictado (preview/confirm §20)."""
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    _forzar_nativo(monkeypatch)
    u = usuario_factory(rol="super_admin")
    fake, _ = _fake_chatear([
        _res(texto="Te propongo esto", tool_calls=[
            ToolCall("c1", "crear_recado", {"destinatarios_slugs": [], "cuerpo": "hola"})]),
        _res("Listo."),
    ])
    monkeypatch.setattr(la, "chatear", fake)

    res = conversar(mensaje="mándale un recado a @ana", usuario=u, conversacion=_conv(u))
    dictado = res["dictado"]
    assert dictado is not None
    assert dictado.acciones.count() == 1
    assert res["mensajes"][-1].tipo == "accion"


def test_prohibidos_no_son_tools_de_propuesta(usuario_factory):
    """Los tipos prohibidos NO se exponen como tools de propuesta; y
    `_persistir_acciones_chat` los filtra aunque llegaran (defensa en profundidad)."""
    from apps.el_dictado.services_chat import _persistir_acciones_chat

    import capacidades
    from lib.dictado_catalogo import COMANDOS_PROHIBIDOS
    u = usuario_factory(rol="super_admin")
    nombres = {s["nombre"] for s in capacidades.specs_chat(u, modos=("propuesta",))}
    for prohibido in COMANDOS_PROHIBIDOS:
        assert prohibido["tipo"] not in nombres
    d = _persistir_acciones_chat(
        acciones_raw=[{"tipo": "modificar_ajustes", "descripcion": "x", "payload": {}}],
        usuario=u, chalan="anthropic")
    assert d.acciones.count() == 0


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


# ── "propone pero no aplica" ahora es estructuralmente imposible ───────────────
# Cada propuesta llama un tool cuyo nombre ES un tipo válido (nombre == tipo), así
# que el modelo no puede proponer una acción con tipo inválido o ausente.

def test_tools_de_propuesta_cubren_las_acciones(usuario_factory):
    """Las acciones de escritura son tools de propuesta cuyo nombre ES el tipo."""
    import capacidades
    u = usuario_factory(rol="super_admin")
    specs = capacidades.specs_chat(u, modos=("propuesta",))
    nombres = {s["nombre"] for s in specs}
    assert "crear_mandado" in nombres and "crear_tarea" in nombres
    for s in specs:
        assert capacidades.es_propuesta(s["nombre"])


def test_sin_propuestas_cierra_con_texto_no_dictado(monkeypatch, usuario_factory):
    """Si el turno no bufferea ninguna propuesta, cierra con texto — nunca deja una
    tarjeta de acción vacía (el viejo bug 0/0 ya no puede ocurrir)."""
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    _forzar_nativo(monkeypatch)
    u = usuario_factory(rol="super_admin")
    fake, _ = _fake_chatear([_res("Necesito más detalle para proponerte algo.")])
    monkeypatch.setattr(la, "chatear", fake)

    res = conversar(mensaje="haz algo", usuario=u, conversacion=_conv(u))
    assert res["dictado"] is None
    assert res["mensajes"][-1].tipo == "texto"
