"""Verificación de un registro del Checador por El Chalán (S-Checador-V14).

Oscar: "me gustaría que el AI pudiera verificarlo y así no depender de que el
runner lo haga". El Chalán lee la nota, el destino (cliente/proveedor/contacto)
y la tarea ligada y clasifica el registro como **visita** o **tarea cumplida**,
y valora si la tarea quedó completada, con una confianza y un resumen corto.

Diseño defensivo (mismo patrón que `categorizador_ia`/`precio_ia`): NUNCA lanza.
Persiste el veredicto en los campos `ia_*` de la Visita; si el LLM no responde
o el JSON es ilegible, los deja como estaban y devuelve `{ok: False, error}`.
Es un apoyo: el propósito que marcó el runner se conserva en `proposito` y el
del AI en `ia_proposito` (la propiedad `proposito_efectivo` prefiere el del AI).
"""

from __future__ import annotations

import json
import re

_MAX_TOKENS = 220


def _parsear_json(texto: str) -> dict | None:
    if not texto:
        return None
    limpio = re.sub(r"^```(?:json)?", "", texto.strip()).strip()
    limpio = re.sub(r"```$", "", limpio).strip()
    m = re.search(r"\{.*\}", limpio, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def verificar_visita_ia(visita, *, usuario=None) -> dict:
    """Clasifica y verifica `visita`. Persiste el veredicto en sus campos `ia_*`.

    Devuelve `{ok, proposito, completada, confianza, resumen, error}`. Nunca
    lanza — pensado para llamarse en `transaction.on_commit` (best-effort)."""
    from django.utils import timezone

    nota = (getattr(visita, "nota", "") or "").strip()
    tarea = getattr(visita, "tarea", None)
    tarea_txt = ""
    if tarea is not None:
        tarea_txt = (getattr(tarea, "titulo", "") or "").strip()
        desc = (getattr(tarea, "descripcion", "") or "").strip()
        if desc:
            tarea_txt += f" — {desc[:200]}"

    # Sin señal alguna no hay nada que verificar.
    if not nota and not tarea_txt:
        return {"ok": False, "error": "Sin nota ni tarea ligada que verificar."}

    system = (
        "Eres El Chalán de Learning Center. Clasificas un registro de campo del "
        "Checador hecho por un colaborador que llegó a un POI (cliente, proveedor "
        "o contacto). Decide si fue una VISITA (pasó a ver/atender) o una TAREA "
        "cumplida (fue a entregar, recoger o completar un encargo concreto), y si "
        "hay tarea ligada, si parece COMPLETADA.\n"
        "Responde SOLO JSON estricto, sin texto fuera:\n"
        '{"proposito": "visita"|"tarea", "completada": true|false|null, '
        '"confianza": 0.0-1.0, "resumen": "<≤140 caracteres>"}\n'
        "Si no hay tarea ligada, `completada` = null. Sé conservador: si dudas, "
        'proposito="visita" y confianza<=0.5.'
    )
    user = (
        f"DESTINO: {visita.destino}\n"
        f"TIPO: {visita.get_tipo_display()}\n"
        f"NOTA DEL COLABORADOR: {nota or '(sin nota)'}\n"
        f"TAREA LIGADA: {tarea_txt or '(ninguna)'}\n\n"
        "¿Fue visita o tarea cumplida?"
    )

    try:
        from chalanes.voz import preludio, reglas
        from lib.analistas import analizar
        from lib.sanear import sanear_contexto
        prompt = preludio("checador_visita") + system + reglas() + "\n\n" + sanear_contexto(user, max_len=2000)
        res = analizar(estacion="checador_visita", prompt=prompt,
                       max_tokens=_MAX_TOKENS, temperatura=0.0,
                       actor_id=getattr(usuario, "pk", None) or getattr(visita.usuario, "pk", None))
    except Exception as exc:  # noqa: BLE001 — nunca tumbar el registro
        return {"ok": False, "error": f"El Chalán no respondió: {str(exc)[:200]}"}

    crudo = _parsear_json(res.texto)
    if crudo is None:
        return {"ok": False, "error": "El Chalán no devolvió un veredicto legible."}

    proposito = "tarea" if str(crudo.get("proposito")).strip().lower() == "tarea" else "visita"
    completada = crudo.get("completada")
    if completada not in (True, False):
        completada = None
    try:
        confianza = max(0.0, min(1.0, float(crudo.get("confianza") or 0)))
    except (ValueError, TypeError):
        confianza = 0.0
    resumen = (str(crudo.get("resumen") or "")).strip()[:200]

    visita.ia_proposito = proposito
    visita.ia_completada = completada
    visita.ia_confianza = confianza
    visita.ia_resumen = resumen
    visita.ia_verificado_en = timezone.now()
    visita.save(update_fields=[
        "ia_proposito", "ia_completada", "ia_confianza", "ia_resumen", "ia_verificado_en",
    ])

    return {"ok": True, "proposito": proposito, "completada": completada,
            "confianza": confianza, "resumen": resumen, "error": ""}


__all__ = ["verificar_visita_ia"]
