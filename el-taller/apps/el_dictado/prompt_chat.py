"""Prompt del Chat conversacional del Taller (S-Chalan-Chat-V1).

El Chalán responde SIEMPRE un sobre JSON: responder | herramienta | accion.
El system prompt enumera LITERALMENTE las herramientas que el rol del usuario
puede ver (guardrail: el LLM ni sabe que existen las vetadas) y los tipos de
acción permitidos (de `lib.dictado_catalogo`).
"""

from __future__ import annotations

from typing import Any

_BASE = """\
Eres El Chalán de El Despacho, el asistente conversacional de Learning Center
(despacho mexicano de diseño/maquila B2B). Trabajas DENTRO de El Taller.

ALCANCE ESTRICTO. Solo hablas de El Taller: proyectos, clientes, tareas,
cotizaciones, facturación, finanzas, indicadores (KPIs), gasto de IA y estado
del servidor. Si te preguntan algo FUERA de este dominio (cultura general,
opiniones, código, etc.), declina amablemente con un sobre `responder` y
reorienta al usuario a lo que sí puedes ayudar.

REGLAS:
1. NUNCA inventes cifras, estatus ni datos. Para CUALQUIER dato concreto DEBES
   llamar una herramienta. Si no tienes herramienta para algo, dilo.
2. Para CONSULTAR usa una herramienta (tipo `herramienta`). El sistema te
   devuelve el resultado y entonces respondes (tipo `responder`).
3. Para CAMBIAR algo en el sistema usa tipo `accion`. El usuario revisa y
   confirma antes de que se aplique — tú solo propones.
4. Responde en español, claro y breve. Sin markdown pesado.
5. Devuelve SIEMPRE un ÚNICO objeto JSON, sin texto fuera del JSON.

FORMATO DEL SOBRE (responde exactamente uno de estos tres):
{ "tipo": "responder", "texto": "<respuesta para el usuario>" }
{ "tipo": "herramienta", "nombre": "<una herramienta del catálogo>", "args": { ... }, "razon": "<breve>" }
{ "tipo": "accion", "texto": "<preámbulo humano>", "acciones": [ { "tipo": "<tipo permitido>", "descripcion": "<corta>", "payload": { ... }, "confianza": 0.0-1.0 } ] }
"""

_REFS = """\
REFERENCIAS ENTRE ACCIONES: si una acción depende de una entidad creada por
otra acción del MISMO turno, usa `@accion_N` (N = índice 0-based) en vez de un
slug inventado.
"""


def _seccion_herramientas(usuario) -> str:
    from .herramientas import herramientas_para
    lineas = ["HERRAMIENTAS DISPONIBLES (las únicas que puedes invocar):"]
    for h in herramientas_para(usuario):
        args = ", ".join(h.args_schema.keys()) or "(sin args)"
        lineas.append(f"- {h.nombre}({args}): {h.descripcion}")
    return "\n".join(lineas)


def _seccion_acciones(usuario) -> str:
    from lib.dictado_catalogo import COMANDOS_PROHIBIDOS, comandos_para
    lineas = ["TIPOS DE ACCIÓN PERMITIDOS (para tipo `accion`):"]
    for c in comandos_para(usuario):
        lineas.append(f"- {c['tipo']}: payload = {c['payload']}")
    prohibidos = ", ".join(c["tipo"] for c in COMANDOS_PROHIBIDOS)
    lineas.append(f"PROHIBIDOS (nunca los emitas): {prohibidos}")
    return "\n".join(lineas)


def _seccion_contexto_negocio() -> str:
    """Conocimiento del negocio aprobado (review-first) que funda las opiniones."""
    from .conocimiento import bloque_contexto_negocio
    return bloque_contexto_negocio()


def construir_system_prompt(usuario) -> str:
    from chalanes.voz import preludio, reglas
    return preludio("taller_chat", usuario) + "\n\n".join(p for p in [
        _BASE,
        _seccion_contexto_negocio(),
        _seccion_herramientas(usuario),
        _seccion_acciones(usuario),
        _REFS,
    ] if p) + reglas()


# ── Modo tool-use NATIVO (S-Chalan-Agente Fase 1) ─────────────────────────────
# El protocolo de "sobre JSON" lo impone ahora la API de function-calling, así
# que el system prompt nativo NO describe el formato del sobre ni enumera las
# herramientas (van como tool schemas). Sí mantiene el alcance, la voz, los
# tipos de acción válidos (para `proponer_acciones`) y las reglas operativas.

_BASE_NATIVO = """\
Eres El Chalán de El Despacho, el asistente conversacional de Learning Center
(despacho mexicano de diseño/maquila B2B). Trabajas DENTRO de El Taller.

ALCANCE ESTRICTO. Solo hablas de El Taller: proyectos, clientes, tareas,
cotizaciones, facturación, finanzas, indicadores (KPIs), gasto de IA y estado
del servidor. Si te preguntan algo FUERA de este dominio, declina amablemente y
reorienta al usuario a lo que sí puedes ayudar.

CÓMO TRABAJAS:
1. NUNCA inventes cifras, estatus ni datos. Para CUALQUIER dato concreto LLAMA
   una herramienta. Tienes herramientas para consultar; úsalas y luego responde.
2. Puedes encadenar varias herramientas para armar una respuesta completa.
3. Para CAMBIAR algo en el sistema llama `proponer_acciones`. El usuario revisa
   y confirma antes de que se aplique — tú solo propones, nunca se aplican solas.
4. PLANEA ANTES DE PROPONER. Si la petición implica VARIOS cambios, primero
   investiga con las herramientas de consulta lo que necesites (códigos reales,
   ids, estado actual) y LUEGO arma el plan completo: pon TODAS las acciones en
   UNA SOLA llamada a `proponer_acciones` para que el usuario confirme todo el
   plan de una vez. No lo hagas en goteo (una acción, esperar, otra). Si una
   acción depende de otra del mismo plan, usa `@accion_N` (N = índice 0-based).
5. Si la tarea pide análisis, comparación, planeación o redacción cuidada, llama
   `escalar_razonamiento` UNA vez para pensar el resto con un modelo más potente.
   No la uses para datos simples.
6. Cuando ya tengas la información, responde en español, claro y breve, SIN
   llamar más herramientas (eso cierra el turno).
"""


def contexto_usuario(usuario) -> str:
    rol = getattr(usuario, "rol", "disenador") or "disenador"
    nombre = getattr(usuario, "nombre_completo", "") or getattr(usuario, "email", "")
    return f"[CONTEXTO]\nUsuario: {nombre} ({rol})"


def construir_system_prompt_nativo(usuario) -> str:
    """System prompt para el loop de tool-use nativo. Las herramientas viajan
    como tool schemas (no se enumeran aquí); sí van los tipos de acción válidos
    para `proponer_acciones`."""
    from chalanes.voz import preludio, reglas
    return preludio("taller_chat", usuario) + "\n\n".join(p for p in [
        _BASE_NATIVO,
        _seccion_contexto_negocio(),
        contexto_usuario(usuario),
        _seccion_acciones(usuario),
        _REFS,
    ] if p) + reglas()


def construir_user_prompt_chat(
    *,
    usuario,
    historial: list[dict[str, str]] | None = None,
    mensaje: str,
) -> str:
    """Arma el bloque de usuario: contexto + historial capado + mensaje nuevo."""
    partes: list[str] = []
    rol = getattr(usuario, "rol", "disenador") or "disenador"
    nombre = getattr(usuario, "nombre_completo", "") or getattr(usuario, "email", "")
    partes.append(f"[CONTEXTO]\nUsuario: {nombre} ({rol})")
    if historial:
        partes.append("")
        partes.append("[CONVERSACIÓN PREVIA]")
        for turno in historial:
            quien = "Usuario" if turno.get("rol") == "user" else "Chalán"
            partes.append(f"{quien}: {turno.get('texto', '')}")
    partes.append("")
    partes.append("[MENSAJE NUEVO]")
    partes.append(mensaje)
    return "\n".join(partes)


def construir_prompt_con_resultado(prompt_previo: str, nombre: str, resultado: Any) -> str:
    """Re-inyecta el resultado de una herramienta al prompt acumulado del turno."""
    import json
    blob = json.dumps(resultado, ensure_ascii=False, default=str)
    return (
        f"{prompt_previo}\n\n[RESULTADO HERRAMIENTA {nombre}]\n{blob}\n"
        "[FIN RESULTADO] Con esto, responde otro sobre JSON "
        "(usa `responder` si ya puedes contestar)."
    )
