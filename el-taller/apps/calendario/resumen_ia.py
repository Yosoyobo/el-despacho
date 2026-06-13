"""El Chalán resume el calendario del usuario (estación `calendario_resumen`).

Junta las entregas de proyectos + tareas con fecha en una ventana (default 14
días) — respetando los permisos del usuario, vía `eventos_por_dia` — y pide al
LLM un resumen ejecutivo: qué viene, qué urge, cómo se ve la carga. NO se
persiste; se muestra en un modal HTMX. Diseño defensivo: nunca lanza — devuelve
`{ok, resumen, error}`.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

_SYSTEM = (
    "Eres El Chalán de Learning Center, un despacho mexicano de diseño y maquila. "
    "Te doy la agenda próxima (entregas de proyectos y tareas con fecha) de una "
    "persona del equipo. Redacta un RESUMEN EJECUTIVO breve en español de México: "
    "qué entregas/tareas vienen, cuáles urgen (las más cercanas o ya vencidas) y "
    "cómo se ve la carga del período. Usa SOLO los datos dados, no inventes fechas "
    "ni proyectos. Máximo 2 párrafos cortos, texto plano, sin encabezados ni viñetas."
)

_MAX_TOKENS = 500

_RE_FENCE = re.compile(r"^```(?:\w+)?|```$", re.IGNORECASE | re.MULTILINE)
_RE_HTML = re.compile(r"<[^>]+>")


def _limpiar(texto: str) -> str:
    texto = _RE_FENCE.sub("", texto or "").strip()
    texto = _RE_HTML.sub("", texto)
    return texto.strip()


def resumir_calendario(*, usuario, dias: int = 14) -> dict:
    """Resume la agenda de `usuario` para los próximos `dias`.

    Devuelve `{ok, resumen, error, dias}`.
    """
    dias = max(1, min(int(dias or 14), 90))
    from apps.calendario.services import eventos_por_dia

    hoy = date.today()
    por_dia = eventos_por_dia(usuario, hoy, hoy + timedelta(days=dias))

    partes: list[str] = [
        f"AGENDA del {hoy:%Y-%m-%d} a {hoy + timedelta(days=dias):%Y-%m-%d} "
        f"(hoy es {hoy:%A %d de %B %Y}, próximos {dias} días):"
    ]
    total = 0
    for fecha in sorted(por_dia):
        for ev in por_dia[fecha]:
            total += 1
            sub = (ev.get("subtitulo") or "").strip()
            sub = f" — {sub}" if sub else ""
            partes.append(
                f"- {fecha:%Y-%m-%d} [{ev.get('tipo', 'evento')}] {ev.get('titulo', '')}{sub}"
            )
    if total == 0:
        partes.append("(No hay entregas ni tareas con fecha en este período.)")
    contexto_txt = "\n".join(partes)

    try:
        from chalanes.voz import preludio, reglas
        from lib.analistas import analizar
        from lib.sanear import sanear_contexto
        prompt = (preludio("calendario_resumen") + _SYSTEM + reglas() + "\n\n"
                  + sanear_contexto(contexto_txt, max_len=8000))
        res = analizar(estacion="calendario_resumen", prompt=prompt,
                       max_tokens=_MAX_TOKENS, temperatura=0.4,
                       actor_id=getattr(usuario, "pk", None))
    except Exception as exc:  # noqa: BLE001 — nunca tumbar la UI
        return {"ok": False, "resumen": "", "error": f"El Chalán no respondió: {str(exc)[:200]}", "dias": dias}

    resumen = _limpiar(res.texto)
    if not resumen:
        return {"ok": False, "resumen": "", "error": "El Chalán devolvió un resumen vacío.", "dias": dias}
    return {"ok": True, "resumen": resumen, "error": "", "dias": dias}


__all__ = ["resumir_calendario"]
