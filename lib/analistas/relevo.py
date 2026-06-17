"""El Relevo — ruteo ACTIVO del pensamiento al mejor modelo (S-Chalan-Agente F1).

Complementa a El Reemplazo (`reemplazo.py`): mientras El Reemplazo cambia de
Chalán cuando uno FALLA, El Relevo elige proactivamente QUÉ Chalán usar según
la dificultad del paso, para no quemar un modelo caro en una consulta trivial
ni quedarse corto en un análisis.

Dos niveles, mapeados a dos estaciones del Cuadro de Chalanes (configurables
por el super_admin en `/chalanes/`):
  - "rapido"   → estación `taller_chat`           (modelo barato, default haiku)
  - "profundo" → estación `taller_chat_profundo`  (modelo fuerte, default sonnet)

El ruteo es heurístico (costo $0). Además el propio agente puede AUTO-escalar
a mitad de un turno con la herramienta `escalar_razonamiento` (lo maneja el
orquestador en services_chat) cuando descubre que la tarea necesita más cabeza.
"""

from __future__ import annotations

ESTACION_RAPIDA = "taller_chat"
ESTACION_PROFUNDA = "taller_chat_profundo"

# Umbral de longitud (chars) a partir del cual una pregunta se considera densa.
_UMBRAL_LARGO = 240
# Pasos de herramienta ya ejecutados a partir de los cuales conviene un modelo
# fuerte para sintetizar lo recabado.
_UMBRAL_PASOS = 2

# Señales de que el usuario pide razonar / analizar / planear / redactar, no
# solo un dato puntual. Acentos incluidos y sin — el match es por substring en
# minúsculas y sin tildes.
_SENALES_PROFUNDO = (
    "analiz", "compar", "recomend", "suger", "estrateg", "planea", "plan de",
    "por que", "porque", "evalua", "optimiz", "proyeccion", "pronost", "tendencia",
    "resume", "resumen", "conviene", "deberia", "mejor opcion", "prioriza",
    "diagnost", "riesgo", "escenario", "margen", "rentab", "propon", "redacta",
    "escribe un", "genera un", "explica por", "cual es la mejor", "que opinas",
    "razona",
)


def _sin_tildes(texto: str) -> str:
    tabla = str.maketrans("áéíóúÁÉÍÓÚüÜ", "aeiouAEIOUuU")
    return texto.translate(tabla)


def nivel(texto: str, *, pasos_previos: int = 0) -> str:
    """Decide 'rapido' | 'profundo' para el SIGUIENTE paso del agente.

    `pasos_previos` = cuántas herramientas ya corrió este turno; tras recabar
    varios datos, la síntesis se beneficia de un modelo fuerte."""
    if pasos_previos >= _UMBRAL_PASOS:
        return "profundo"
    t = _sin_tildes((texto or "").lower())
    if len(t) >= _UMBRAL_LARGO:
        return "profundo"
    if any(s in t for s in _SENALES_PROFUNDO):
        return "profundo"
    return "rapido"


def estacion(nivel_: str) -> str:
    """Mapea el nivel a la estación del Cuadro de Chalanes."""
    return ESTACION_PROFUNDA if nivel_ == "profundo" else ESTACION_RAPIDA


__all__ = ["ESTACION_RAPIDA", "ESTACION_PROFUNDA", "nivel", "estacion"]
