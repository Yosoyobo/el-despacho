"""Tests de la capa de tool-use NATIVO de Los Analistas (S-Chalan-Agente F1).

Cubre el formato por proveedor (Anthropic / OpenAI-family / Gemini), los
parsers de tool-calls, la retrocompatibilidad de `Resultado` y la heurística de
El Relevo. Funciones puras — no pegan a ningún LLM ni necesitan DB.
"""

from __future__ import annotations

import json

from lib.analistas import herramientas_formato as hf
from lib.analistas import relevo
from lib.analistas.base import Resultado, ToolCall


def test_resultado_retrocompatible():
    # Los callers viejos (analizar) no pasan tool_calls/stop_reason.
    r = Resultado(texto="hola", provider="anthropic", modelo="m",
                  prompt_tokens=1, completion_tokens=2, costo_usd=0.0, latencia_ms=10)
    assert r.tool_calls == ()
    assert r.stop_reason == ""


def test_esquema_json_desde_args_schema():
    s = hf.esquema_json({
        "slug": {"tipo": "str", "requerido": True},
        "dias": {"tipo": "int"},
        "modo": {"tipo": "str", "enum": ["a", "b"]},
    })
    assert s["type"] == "object"
    assert s["properties"]["slug"]["type"] == "string"
    assert s["properties"]["dias"]["type"] == "integer"
    assert s["properties"]["modo"]["enum"] == ["a", "b"]
    assert s["required"] == ["slug"]


def test_separar_system():
    sys, resto = hf.separar_system([
        {"rol": "system", "texto": "S"},
        {"rol": "user", "texto": "U"},
    ])
    assert sys == "S"
    assert len(resto) == 1 and resto[0]["rol"] == "user"


def test_aplanar_a_prompt():
    txt = hf.aplanar_a_prompt([
        {"rol": "system", "texto": "Eres X"},
        {"rol": "user", "texto": "hola"},
        {"rol": "tool", "nombre": "gasto_ia", "texto": "{}"},
    ])
    assert "Eres X" in txt and "Usuario: hola" in txt and "gasto_ia" in txt


def test_builders_de_herramientas():
    specs = [
        {"nombre": "mis_tareas", "descripcion": "d", "args_schema": {}},
        {"nombre": "x", "descripcion": "d2",
         "json_schema": {"type": "object", "properties": {"a": {"type": "string"}}}},
    ]
    a = hf.herramientas_anthropic(specs)
    assert a[0]["name"] == "mis_tareas" and "input_schema" in a[0]
    o = hf.herramientas_openai(specs)
    assert o[0]["type"] == "function" and o[0]["function"]["name"] == "mis_tareas"
    g = hf.herramientas_gemini(specs)
    assert g[0]["functionDeclarations"][0]["name"] == "mis_tareas"
    # json_schema crudo se respeta tal cual.
    assert o[1]["function"]["parameters"]["properties"]["a"]["type"] == "string"


def test_mensajes_anthropic_agrupa_tool_results():
    msgs = [
        {"rol": "user", "texto": "hola"},
        {"rol": "assistant", "texto": "",
         "tool_calls": [ToolCall("id1", "gasto_ia", {"dias": 30}), ToolCall("id2", "mis_tareas", {})]},
        {"rol": "tool", "tool_call_id": "id1", "nombre": "gasto_ia", "texto": '{"x":1}'},
        {"rol": "tool", "tool_call_id": "id2", "nombre": "mis_tareas", "texto": '{"y":2}'},
    ]
    out = hf.mensajes_anthropic(msgs)
    assert out[0]["role"] == "user"
    assert out[1]["role"] == "assistant"
    assert sum(1 for b in out[1]["content"] if b["type"] == "tool_use") == 2
    # Los dos tool_result se agrupan en UN solo turno user (lo exige la API).
    assert out[2]["role"] == "user"
    assert len(out[2]["content"]) == 2
    assert all(b["type"] == "tool_result" for b in out[2]["content"])


def test_mensajes_openai_system_assistant_tool():
    msgs = [
        {"rol": "system", "texto": "S"},
        {"rol": "user", "texto": "U"},
        {"rol": "assistant", "texto": "", "tool_calls": [ToolCall("c1", "gasto_ia", {"dias": 30})]},
        {"rol": "tool", "tool_call_id": "c1", "nombre": "gasto_ia", "texto": "{}"},
    ]
    out = hf.mensajes_openai(msgs)
    assert out[0]["role"] == "system"
    assert out[2]["role"] == "assistant"
    assert out[2]["tool_calls"][0]["function"]["name"] == "gasto_ia"
    assert json.loads(out[2]["tool_calls"][0]["function"]["arguments"]) == {"dias": 30}
    assert out[3]["role"] == "tool" and out[3]["tool_call_id"] == "c1"


def test_mensajes_gemini_function_call_y_response():
    msgs = [
        {"rol": "user", "texto": "U"},
        {"rol": "assistant", "texto": "", "tool_calls": [ToolCall("x_0", "gasto_ia", {"dias": 7})]},
        {"rol": "tool", "tool_call_id": "x_0", "nombre": "gasto_ia", "texto": '{"costo":1}'},
    ]
    out = hf.mensajes_gemini(msgs)
    assert out[0]["role"] == "user"
    assert out[1]["role"] == "model"
    assert out[1]["parts"][0]["functionCall"]["name"] == "gasto_ia"
    assert out[2]["parts"][0]["functionResponse"]["name"] == "gasto_ia"
    assert out[2]["parts"][0]["functionResponse"]["response"] == {"costo": 1}


def test_parsear_anthropic_tool_use():
    data = {
        "content": [
            {"type": "text", "text": "déjame ver"},
            {"type": "tool_use", "id": "tu1", "name": "gasto_ia", "input": {"dias": 30}},
        ],
        "usage": {"input_tokens": 5, "output_tokens": 3},
        "stop_reason": "tool_use", "model": "claude-x",
    }
    r = hf.parsear_anthropic(data, provider="anthropic", modelo="m", latencia_ms=1,
                             precio_in=0.0, precio_out=0.0)
    assert r.texto == "déjame ver"
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].nombre == "gasto_ia" and r.tool_calls[0].args == {"dias": 30}
    assert r.stop_reason == "tool_use"


def test_parsear_openai_tool_calls():
    data = {
        "choices": [{"message": {"content": None,
                                 "tool_calls": [{"id": "c1", "function": {"name": "mis_tareas", "arguments": "{}"}}]},
                     "finish_reason": "tool_calls"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    r = hf.parsear_openai(data, provider="openai", modelo="m", latencia_ms=1,
                          precio_in=0.0, precio_out=0.0)
    assert r.tool_calls[0].nombre == "mis_tareas"
    assert r.stop_reason == "tool_calls"


def test_parsear_openai_arguments_malformados_no_lanza():
    data = {"choices": [{"message": {"content": None,
            "tool_calls": [{"id": "c1", "function": {"name": "x", "arguments": "no-json"}}]}}]}
    r = hf.parsear_openai(data, provider="openai", modelo="m", latencia_ms=1,
                          precio_in=0.0, precio_out=0.0)
    assert r.tool_calls[0].args == {}  # fallback tolerante


def test_parsear_gemini_function_call():
    data = {
        "candidates": [{"content": {"parts": [{"functionCall": {"name": "gasto_ia", "args": {"dias": 7}}}]},
                        "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 2, "candidatesTokenCount": 1},
    }
    r = hf.parsear_gemini(data, provider="gemini", modelo="m", latencia_ms=1,
                          precio_in=0.0, precio_out=0.0)
    assert r.tool_calls[0].nombre == "gasto_ia" and r.tool_calls[0].args == {"dias": 7}


# ── El Relevo ─────────────────────────────────────────────────────────────────

def test_relevo_rapido_para_dato_simple():
    assert relevo.nivel("¿cuántos proyectos hay?") == "rapido"


def test_relevo_profundo_por_senal():
    assert relevo.nivel("analiza la rentabilidad y recomiéndame qué priorizar") == "profundo"


def test_relevo_profundo_por_pasos_acumulados():
    assert relevo.nivel("dato", pasos_previos=2) == "profundo"


def test_relevo_mapea_estacion():
    assert relevo.estacion("profundo") == relevo.ESTACION_PROFUNDA == "taller_chat_profundo"
    assert relevo.estacion("rapido") == relevo.ESTACION_RAPIDA == "taller_chat"
