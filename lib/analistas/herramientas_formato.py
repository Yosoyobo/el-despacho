"""Formato de tool-use NATIVO para Los Analistas (S-Chalan-Agente Fase 1).

Convierte entre el formato CANÓNICO del repo y la API de function-calling de
cada proveedor. Espejo de `multimodal.py` pero para herramientas + conversación
multi-turno con tool_use/tool_result.

Mensaje canónico (dict):
    {"rol": "system"|"user"|"assistant"|"tool",
     "texto": str,                       # contenido textual del turno
     "imagenes": [{base64, media_type}], # solo en el turno user con visión
     "tool_calls": [ToolCall|dict],      # solo assistant: lo que el modelo pidió
     "tool_call_id": str,                # solo tool: id que casa con la tool_call
     "nombre": str}                      # solo tool: nombre de la herramienta

Spec de herramienta (dict):
    {"nombre": str, "descripcion": str, "args_schema": {...}}   ó
    {"nombre": str, "descripcion": str, "json_schema": {...}}   # JSON Schema crudo

Cada proveedor tiene su builder de tools, su builder de mensajes y su parser de
respuesta. El parser devuelve un `Resultado` con `tool_calls` lleno cuando el
modelo pidió herramientas.
"""

from __future__ import annotations

import json

from .base import Resultado, ToolCall

# Mini-tipo del repo (herramientas.py) → tipo JSON Schema.
_TIPO_JSON = {
    "str": "string",
    "int": "integer",
    "bool": "boolean",
    "dict": "object",
    "any": "object",
}


# ── Esquema de argumentos ─────────────────────────────────────────────────────

def esquema_json(args_schema: dict) -> dict:
    """Convierte el `args_schema` mini del repo a JSON Schema (object)."""
    props: dict = {}
    requeridos: list[str] = []
    for arg, spec in (args_schema or {}).items():
        jt = _TIPO_JSON.get(spec.get("tipo", "str"), "string")
        prop: dict = {"type": jt}
        if spec.get("enum"):
            prop["enum"] = list(spec["enum"])
        if spec.get("descripcion"):
            prop["description"] = spec["descripcion"]
        props[arg] = prop
        if spec.get("requerido"):
            requeridos.append(arg)
    schema: dict = {"type": "object", "properties": props}
    if requeridos:
        schema["required"] = requeridos
    return schema


def _params(spec: dict) -> dict:
    return spec.get("json_schema") or esquema_json(spec.get("args_schema") or {})


# ── Tool-call: campos sin importar si es ToolCall o dict ──────────────────────

def _tc_fields(tc) -> tuple[str, str, dict]:
    if isinstance(tc, ToolCall):
        return tc.id, tc.nombre, tc.args
    return (tc.get("id") or "", tc.get("nombre") or tc.get("name") or "", tc.get("args") or {})


def _loads_args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def separar_system(mensajes: list[dict]) -> tuple[str, list[dict]]:
    """Separa el/los turno(s) `system` (concatenados) del resto."""
    sys_partes = [m.get("texto") or "" for m in mensajes if m.get("rol") == "system"]
    resto = [m for m in mensajes if m.get("rol") != "system"]
    return ("\n\n".join(p for p in sys_partes if p), resto)


def aplanar_a_prompt(mensajes: list[dict]) -> str:
    """Aplana la conversación a un único prompt (modo degradación a texto)."""
    partes: list[str] = []
    for m in mensajes:
        rol = m.get("rol")
        txt = (m.get("texto") or "").strip()
        if rol == "system" and txt:
            partes.append(txt)
        elif rol == "user" and txt:
            partes.append(f"Usuario: {txt}")
        elif rol == "assistant" and txt:
            partes.append(f"Asistente: {txt}")
        elif rol == "tool":
            partes.append(f"[Resultado {m.get('nombre', '')}]: {txt}")
    return "\n\n".join(partes)


# ── Anthropic (Messages API: tool_use / tool_result) ──────────────────────────

def herramientas_anthropic(specs: list[dict]) -> list[dict]:
    return [
        {"name": s["nombre"], "description": s.get("descripcion", ""), "input_schema": _params(s)}
        for s in specs
    ]


def mensajes_anthropic(resto: list[dict]) -> list[dict]:
    """`resto` = mensajes SIN system (va aparte en el body). Agrupa tool_results
    consecutivos en un solo turno `user` (lo exige la Messages API)."""
    from .multimodal import contenido_anthropic, normalizar_imagenes
    out: list[dict] = []
    i = 0
    n = len(resto)
    while i < n:
        m = resto[i]
        rol = m.get("rol")
        if rol == "tool":
            bloques: list[dict] = []
            while i < n and resto[i].get("rol") == "tool":
                tm = resto[i]
                bloques.append({
                    "type": "tool_result",
                    "tool_use_id": tm.get("tool_call_id") or "",
                    "content": tm.get("texto") or "",
                })
                i += 1
            out.append({"role": "user", "content": bloques})
            continue
        if rol == "user":
            imgs = normalizar_imagenes(m.get("imagenes"))
            contenido = contenido_anthropic(m.get("texto") or "", imgs) if imgs else (m.get("texto") or "")
            out.append({"role": "user", "content": contenido})
        elif rol == "assistant":
            bloques = []
            if m.get("texto"):
                bloques.append({"type": "text", "text": m["texto"]})
            for tc in m.get("tool_calls") or []:
                tid, nom, args = _tc_fields(tc)
                bloques.append({"type": "tool_use", "id": tid, "name": nom, "input": args})
            out.append({"role": "assistant", "content": bloques or ""})
        i += 1
    return out


def parsear_anthropic(data: dict, *, provider: str, modelo: str, latencia_ms: int,
                      precio_in: float, precio_out: float) -> Resultado:
    bloques = data.get("content") or []
    texto = "".join(b.get("text", "") for b in bloques if b.get("type") == "text")
    tcs = [
        ToolCall(id=b.get("id") or "", nombre=b.get("name") or "", args=b.get("input") or {})
        for b in bloques if b.get("type") == "tool_use"
    ]
    usage = data.get("usage") or {}
    pt = int(usage.get("input_tokens") or 0)
    ct = int(usage.get("output_tokens") or 0)
    return Resultado(
        texto=texto, provider=provider, modelo=data.get("model") or modelo,
        prompt_tokens=pt, completion_tokens=ct,
        costo_usd=round(pt * precio_in + ct * precio_out, 6), latencia_ms=latencia_ms,
        tool_calls=tuple(tcs), stop_reason=data.get("stop_reason") or "",
    )


# ── OpenAI / Deepseek / MiMo (chat/completions: tool_calls) ───────────────────

def herramientas_openai(specs: list[dict]) -> list[dict]:
    return [
        {"type": "function",
         "function": {"name": s["nombre"], "description": s.get("descripcion", ""),
                      "parameters": _params(s)}}
        for s in specs
    ]


def mensajes_openai(mensajes: list[dict]) -> list[dict]:
    """Incluye el system como mensaje de rol `system` (no se separa)."""
    from .multimodal import contenido_openai, normalizar_imagenes
    out: list[dict] = []
    for m in mensajes:
        rol = m.get("rol")
        if rol == "system":
            out.append({"role": "system", "content": m.get("texto") or ""})
        elif rol == "user":
            imgs = normalizar_imagenes(m.get("imagenes"))
            contenido = contenido_openai(m.get("texto") or "", imgs) if imgs else (m.get("texto") or "")
            out.append({"role": "user", "content": contenido})
        elif rol == "assistant":
            msg: dict = {"role": "assistant", "content": m.get("texto") or None}
            tcs = m.get("tool_calls") or []
            if tcs:
                lista = []
                for idx, tc in enumerate(tcs):
                    tid, nom, args = _tc_fields(tc)
                    lista.append({
                        "id": tid or f"call_{idx}", "type": "function",
                        "function": {"name": nom, "arguments": json.dumps(args, ensure_ascii=False)},
                    })
                msg["tool_calls"] = lista
            out.append(msg)
        elif rol == "tool":
            out.append({"role": "tool", "tool_call_id": m.get("tool_call_id") or "",
                        "content": m.get("texto") or ""})
    return out


def parsear_openai(data: dict, *, provider: str, modelo: str, latencia_ms: int,
                   precio_in: float, precio_out: float) -> Resultado:
    choices = data.get("choices") or []
    msg = (choices[0].get("message") if choices else {}) or {}
    texto = msg.get("content") or ""
    tcs = []
    for tc in (msg.get("tool_calls") or []):
        fn = tc.get("function") or {}
        tcs.append(ToolCall(id=tc.get("id") or "", nombre=fn.get("name") or "",
                            args=_loads_args(fn.get("arguments"))))
    usage = data.get("usage") or {}
    pt = int(usage.get("prompt_tokens") or 0)
    ct = int(usage.get("completion_tokens") or 0)
    fin = (choices[0].get("finish_reason") if choices else "") or ""
    return Resultado(
        texto=texto, provider=provider, modelo=data.get("model") or modelo,
        prompt_tokens=pt, completion_tokens=ct,
        costo_usd=round(pt * precio_in + ct * precio_out, 6), latencia_ms=latencia_ms,
        tool_calls=tuple(tcs), stop_reason=fin,
    )


# ── Gemini (generateContent: functionCall / functionResponse) ─────────────────

def herramientas_gemini(specs: list[dict]) -> list[dict]:
    return [{"functionDeclarations": [
        {"name": s["nombre"], "description": s.get("descripcion", ""), "parameters": _params(s)}
        for s in specs
    ]}]


def _gemini_response_obj(texto: str) -> dict:
    if not texto:
        return {"result": ""}
    try:
        parsed = json.loads(texto)
    except (ValueError, TypeError):
        return {"result": texto}
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def mensajes_gemini(resto: list[dict]) -> list[dict]:
    """`resto` = mensajes SIN system (el system va en systemInstruction aparte)."""
    from .multimodal import normalizar_imagenes, partes_gemini
    out: list[dict] = []
    for m in resto:
        rol = m.get("rol")
        if rol == "user":
            imgs = normalizar_imagenes(m.get("imagenes"))
            partes = partes_gemini(m.get("texto") or "", imgs) if imgs else [{"text": m.get("texto") or ""}]
            out.append({"role": "user", "parts": partes})
        elif rol == "assistant":
            partes = []
            if m.get("texto"):
                partes.append({"text": m["texto"]})
            for tc in m.get("tool_calls") or []:
                _, nom, args = _tc_fields(tc)
                partes.append({"functionCall": {"name": nom, "args": args}})
            out.append({"role": "model", "parts": partes})
        elif rol == "tool":
            out.append({"role": "user", "parts": [
                {"functionResponse": {"name": m.get("nombre") or "",
                                      "response": _gemini_response_obj(m.get("texto") or "")}}
            ]})
    return out


def parsear_gemini(data: dict, *, provider: str, modelo: str, latencia_ms: int,
                   precio_in: float, precio_out: float) -> Resultado:
    cands = data.get("candidates") or []
    partes = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
    texto = "".join(p.get("text", "") for p in partes if "text" in p)
    tcs = []
    for idx, p in enumerate(partes):
        fc = p.get("functionCall")
        if fc:
            tcs.append(ToolCall(id=f"{fc.get('name', '')}_{idx}",
                                nombre=fc.get("name") or "", args=fc.get("args") or {}))
    usage = data.get("usageMetadata") or {}
    pt = int(usage.get("promptTokenCount") or 0)
    ct = int(usage.get("candidatesTokenCount") or 0)
    fin = (cands[0].get("finishReason") if cands else "") or ""
    return Resultado(
        texto=texto, provider=provider, modelo=modelo,
        prompt_tokens=pt, completion_tokens=ct,
        costo_usd=round(pt * precio_in + ct * precio_out, 6), latencia_ms=latencia_ms,
        tool_calls=tuple(tcs), stop_reason=fin,
    )


__all__ = [
    "esquema_json", "separar_system", "aplanar_a_prompt",
    "herramientas_anthropic", "mensajes_anthropic", "parsear_anthropic",
    "herramientas_openai", "mensajes_openai", "parsear_openai",
    "herramientas_gemini", "mensajes_gemini", "parsear_gemini",
]
