"""El Chalán le pone una LECTURA al reporte de pendientes del Dashboard.

LC 2026-08-04 (Oscar): «vamos a cambiar a que este botón en el dashboard use IA,
como el botón de la página del calendario». Ese botón hace exactamente esto: las
secciones se arman con consultas —un reporte operativo tiene que ser EXACTO— y el
Chalán agrega arriba una lectura corta de la carga, que es lo único que de verdad
requiere criterio.

Reusa la estación `calendario_resumen` (ya configurada en Gerencia → Chalanes):
el trabajo es el mismo —leer una agenda y decir cómo se ve—, así que no hace
falta una estación nueva ni su migración de seed.

Diseño defensivo: nunca lanza. Devuelve `{ok, lectura, error}`; si El Chalán no
responde, el reporte se muestra igual sin la frase.
"""

from __future__ import annotations

import re

_SYSTEM = (
    "Eres El Chalán de Learning Center, un despacho mexicano de diseño y maquila. "
    "Te doy el reporte de pendientes del taller (tareas urgentes, pendientes por "
    "persona, mandados, entregas, facturas por emitir y por cobrar). Devuelve "
    "MÁXIMO DOS FRASES cortas en español de México: qué es lo que más urge hoy y "
    "qué conviene destrabar primero. Usa SOLO los datos dados, no inventes ni "
    "repitas listas. Sin encabezados, sin viñetas, sin saludos, sin markdown."
)

_MAX_TOKENS = 200

_RE_FENCE = re.compile(r"^```(?:\w+)?|```$", re.IGNORECASE | re.MULTILINE)
_RE_HTML = re.compile(r"<[^>]+>")
_RE_ENFASIS = re.compile(r"(\*\*|__)(.+?)\1", re.DOTALL)


def _limpiar(texto: str) -> str:
    texto = _RE_FENCE.sub("", texto or "").strip()
    texto = _RE_HTML.sub("", texto)
    return _RE_ENFASIS.sub(r"\2", texto).strip()


def lectura_de_pendientes(*, usuario, contexto_txt: str) -> dict:
    """Dos frases del Chalán sobre los pendientes ya reunidos.

    Devuelve `{ok, lectura, error}`. Nunca lanza.
    """
    if not (contexto_txt or "").strip():
        return {"ok": False, "lectura": "", "error": "Sin pendientes que leer."}
    try:
        from chalanes.voz import preludio, reglas
        from lib.analistas import analizar
        from lib.sanear import sanear_contexto
        prompt = (preludio("calendario_resumen") + _SYSTEM + reglas() + "\n\n"
                  + sanear_contexto(contexto_txt, max_len=6000))
        res = analizar(estacion="calendario_resumen", prompt=prompt,
                       max_tokens=_MAX_TOKENS, temperatura=0.3,
                       actor_id=getattr(usuario, "pk", None))
    except Exception as exc:  # noqa: BLE001 — nunca tumbar la UI
        return {"ok": False, "lectura": "", "error": f"El Chalán no respondió: {str(exc)[:200]}"}

    lectura = _limpiar(res.texto)
    if not lectura:
        return {"ok": False, "lectura": "", "error": "El Chalán devolvió una lectura vacía."}
    return {"ok": True, "lectura": lectura, "error": ""}


__all__ = ["lectura_de_pendientes"]
