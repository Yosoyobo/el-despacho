"""El Chalán le pone una LECTURA al resumen del calendario (estación
`calendario_resumen`).

LC 2026-07-29 (Oscar): «el resumen ejecutivo debería dar info muy resumida» y con
un formato exacto (Hoy / Esta semana / Tareas / Siguientes entregas). Ese formato
no tiene nada que interpretar, así que **las secciones las arma
`apps.calendario.resumen` con consultas** — exactas, instantáneas y gratis.

Aquí queda lo único que sí requiere criterio: **una línea** que diga cómo se ve
la carga. Diseño defensivo: nunca lanza — devuelve `{ok, lectura, error}`, y si
El Chalán no responde el resumen se muestra igual sin ella.
"""

from __future__ import annotations

import re

_SYSTEM = (
    "Eres El Chalán de Learning Center, un despacho mexicano de diseño y maquila. "
    "Te doy la agenda ya resumida de una persona del equipo. Devuelve UNA SOLA "
    "FRASE (máximo 25 palabras) en español de México diciendo cómo se ve la carga "
    "y qué es lo que más urge. Usa SOLO los datos dados, no inventes nada. Sin "
    "encabezados, sin viñetas, sin saludos: sólo la frase."
)

_MAX_TOKENS = 120

_RE_FENCE = re.compile(r"^```(?:\w+)?|```$", re.IGNORECASE | re.MULTILINE)
_RE_HTML = re.compile(r"<[^>]+>")


def _limpiar(texto: str) -> str:
    texto = _RE_FENCE.sub("", texto or "").strip()
    texto = _RE_HTML.sub("", texto)
    return texto.strip()


def lectura_de_carga(*, usuario, contexto_txt: str) -> dict:
    """Una frase del Chalán sobre la carga, a partir del resumen ya armado.

    Devuelve `{ok, lectura, error}`. Nunca lanza: si falla, el resumen se muestra
    sin la frase.
    """
    if not (contexto_txt or "").strip():
        return {"ok": False, "lectura": "", "error": "Sin agenda que leer."}
    try:
        from chalanes.voz import preludio, reglas
        from lib.analistas import analizar
        from lib.sanear import sanear_contexto
        prompt = (preludio("calendario_resumen") + _SYSTEM + reglas() + "\n\n"
                  + sanear_contexto(contexto_txt, max_len=4000))
        res = analizar(estacion="calendario_resumen", prompt=prompt,
                       max_tokens=_MAX_TOKENS, temperatura=0.3,
                       actor_id=getattr(usuario, "pk", None))
    except Exception as exc:  # noqa: BLE001 — nunca tumbar la UI
        return {"ok": False, "lectura": "", "error": f"El Chalán no respondió: {str(exc)[:200]}"}

    lectura = _limpiar(res.texto)
    if not lectura:
        return {"ok": False, "lectura": "", "error": "El Chalán devolvió una lectura vacía."}
    return {"ok": True, "lectura": lectura, "error": ""}


__all__ = ["lectura_de_carga"]
