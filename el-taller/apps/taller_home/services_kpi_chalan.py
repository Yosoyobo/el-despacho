"""S2b.5 — NL→DSL: pregunta en lenguaje natural → DSL JSON validado.

El Chalán Claudio (estación `kpi_dsl`) traduce. NUNCA se ejecuta sin
validar primero. El system prompt enumera el whitelist literalmente para
reducir la chance de generar algo inválido.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from lib.kpi_dsl import (
    AGREGACIONES,
    ENTIDADES,
    OPS_FILTRO,
    VENTANAS_TIEMPO,
    ValidacionError,
    ejecutar_con_preview,
    validar,
)

logger = logging.getLogger(__name__)


def _system_prompt() -> str:
    entidades_doc = []
    for nombre, cfg in ENTIDADES.items():
        campos_filt = ", ".join(cfg["campos_filtrables"]) or "<ninguno>"
        campos_num = ", ".join(cfg["campos_numericos"]) or "<ninguno>"
        entidades_doc.append(f"- {nombre}: filtros={campos_filt} · agregables={campos_num}")
    return f"""\
Eres El Chalán de KPIs custom de El Despacho (Learning Center). Traduces
una pregunta del usuario sobre métricas del negocio a un DSL JSON acotado.

NUNCA respondas SQL, ORM, ni texto fuera del JSON. SOLO el JSON.

ENTIDADES Y CAMPOS PERMITIDOS:
{chr(10).join(entidades_doc)}

AGREGACIONES: {", ".join(AGREGACIONES)}
OPERADORES DE FILTRO: {", ".join(OPS_FILTRO)}
VENTANAS DE TIEMPO: {", ".join(VENTANAS_TIEMPO)}
ALCANCE DE USUARIO: "todos" | "mio" (filtra por autor/asignado).

FORMATO:
{{
  "entidad": "...",
  "agregacion": "count" | "sum" | "avg" | "min" | "max",
  "campo": "..." (sólo si agregacion≠count),
  "filtros": [{{ "campo": "...", "op": "...", "valor": ... }}],
  "ventana_tiempo": "siempre" | "ultimos_7d" | "ultimos_30d" | "este_mes" | "este_ano",
  "alcance_usuario": "todos" | "mio",
  "titulo_sugerido": "Título humano corto",
  "categoria_sugerida": "operacion" | "tareas" | "buzon" | "recados" | "cartera" | "dinero" | "custom"
}}

Si la pregunta no se puede expresar dentro del DSL, responde:
{{"error": "Explicación humana corta de por qué no se puede."}}
"""


def nl_a_dsl(*, texto: str, usuario, max_tokens: int = 1500) -> dict:
    """Traduce un texto NL a un DSL validado. Devuelve un dict con la
    siguiente forma:

    - `{"ok": True, "definicion": <dsl normalizado>, "titulo_sugerido": str,
       "categoria_sugerida": str, "preview": <resultado_ejecutado>}`
    - `{"ok": False, "error": str}` (cualquier falla — LLM, validación, etc.)
    """
    from chalanes.voz import preludio
    from lib.analistas import analizar
    prompt = preludio("kpi_dsl") + _system_prompt() + "\n\nPREGUNTA DEL USUARIO:\n" + texto
    try:
        resultado = analizar(
            estacion="kpi_dsl", prompt=prompt,
            max_tokens=max_tokens, temperatura=0.2,
            actor_id=getattr(usuario, "pk", None),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("kpi_dsl LLM falló: %s", exc)
        return {"ok": False, "error": f"El Chalán no respondió: {exc}"}

    parsed = _parsear_json(resultado.texto)
    if parsed is None:
        return {"ok": False, "error": "El Chalán respondió algo que no es JSON válido."}
    if "error" in parsed:
        return {"ok": False, "error": str(parsed["error"])[:300]}

    titulo_sugerido = (parsed.pop("titulo_sugerido", None) or "").strip()[:100]
    categoria_sugerida = (parsed.pop("categoria_sugerida", None) or "custom").strip()[:30]

    try:
        normalizada = validar(parsed)
    except ValidacionError as exc:
        return {"ok": False, "error": str(exc)}

    preview = ejecutar_con_preview(normalizada, usuario=usuario)
    if not preview["ok"]:
        return {"ok": False, "error": preview["error"]}

    return {
        "ok": True,
        "definicion": normalizada,
        "titulo_sugerido": titulo_sugerido or _titulo_fallback(normalizada),
        "categoria_sugerida": categoria_sugerida or "custom",
        "preview": preview["resultado"],
    }


def _parsear_json(texto: str) -> Any:
    if not texto:
        return None
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio < 0 or fin < inicio:
        return None
    try:
        return json.loads(texto[inicio : fin + 1])
    except json.JSONDecodeError:
        return None


def _titulo_fallback(definicion: dict) -> str:
    base = f"{definicion['agregacion']} {definicion['entidad']}"
    if definicion.get("ventana_tiempo") and definicion["ventana_tiempo"] != "siempre":
        base += f" ({definicion['ventana_tiempo']})"
    return base[:100]
