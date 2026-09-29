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
    ValidacionError,
    describir,
    ejecutar_con_preview,
    resumen_para_prompt,
    validar,
)

logger = logging.getLogger(__name__)


def _system_prompt() -> str:
    """El esquema v2 sale de `lib.kpi_dsl` (`resumen_para_prompt`): agregar
    un campo o una entidad a la whitelist lo agrega aquí solo."""
    return f"""\
Eres El Chalán de KPIs custom de El Despacho (Learning Center). Traduces
una pregunta del usuario sobre métricas del negocio a un DSL JSON acotado.

NUNCA respondas SQL, ORM, ni texto fuera del JSON. SOLO el JSON.
Usa SÓLO las entidades, campos, agrupaciones y duraciones de esta lista.

{resumen_para_prompt()}
FORMATO (las llaves marcadas «opcional» se omiten si no hacen falta):
{{
  "entidad": "...",
  "agregacion": "count" | "sum" | "avg" | "min" | "max",
  "campo": "..."                      (sólo si agregacion≠count y no hay duracion),
  "duracion": "..."                   (opcional: una duración de la entidad, con avg/min/max/sum),
  "filtros": [{{ "campo": "...", "op": "...", "valor": ... }}],
  "ventana_tiempo": "...",
  "campo_fecha": "..."                (opcional: otra fecha de la entidad para la ventana),
  "alcance_usuario": "todos" | "mio",
  "tipo": "valor" | "porcentaje"      (opcional),
  "filtros_numerador": [...]          (sólo con tipo=porcentaje: la parte que se cuenta),
  "agrupar_por": "..."                (opcional), "top": 10 (opcional, 1-50),
  "comparar": true                    (opcional: contra el periodo anterior; no con "siempre"),
  "formato": "..."                    (opcional), "direccion": "sube" | "baja" | "neutro" (opcional),
  "titulo_sugerido": "Título humano corto",
  "categoria_sugerida": "operacion" | "tareas" | "buzon" | "recados" | "cartera" | "dinero" | "custom"
}}

FILTROS ESPECIALES:
- {{"campo": "completada_en", "op": "vacio", "valor": true}} → sin valor (false → con valor).
- Fechas: {{"campo": "fecha_compromiso", "op": "lt", "valor": "hoy"}}; también "hace_N_dias",
  "en_N_dias" o "AAAA-MM-DD".
- Contra otro campo: {{"campo": "completada_en", "op": "lte", "campo_ref": "fecha_compromiso"}}.
- "in" lleva lista: {{"campo": "estado", "op": "in", "valor": ["a", "b"]}}.

EJEMPLO «% de tareas cerradas a tiempo este mes»:
{{"entidad": "tarea", "agregacion": "count", "tipo": "porcentaje",
  "filtros": [{{"campo": "completada_en", "op": "vacio", "valor": false}}],
  "filtros_numerador": [{{"campo": "completada_en", "op": "lte", "campo_ref": "fecha_compromiso"}}],
  "ventana_tiempo": "este_mes", "alcance_usuario": "todos", "direccion": "sube"}}

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
    from chalanes.voz import preludio, reglas
    from lib.analistas import analizar
    prompt = preludio("kpi_dsl") + _system_prompt() + reglas() + "\n\nPREGUNTA DEL USUARIO:\n" + texto
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
    """La frase de lo que mide, recortada (antes: «count proyecto (este_mes)»)."""
    return describir(definicion).rstrip(".")[:100]
