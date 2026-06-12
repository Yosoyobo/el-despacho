"""El Chalán resume la actividad de un proyecto (estación `comunicacion`, S4).

Junta el feed de `ActividadProyecto` + comentarios visibles (respetando
`es_interno`) + tareas con su estado, y pide al LLM un resumen ejecutivo en un
párrafo. NO se persiste — se muestra en un modal HTMX. Diseño defensivo: nunca
lanza — devuelve `{ok, resumen, error}`.
"""

from __future__ import annotations

import re

_SYSTEM = (
    "Eres El Chalán de Learning Center, un despacho mexicano de diseño y maquila. "
    "Te doy la actividad reciente de un proyecto (eventos, comentarios y tareas "
    "con su estado). Redacta un RESUMEN EJECUTIVO en UN solo párrafo, español de "
    "México, profesional y conciso: dónde está el proyecto, qué se ha hecho y qué "
    "falta o está bloqueado. Usa SOLO los datos dados, no inventes. Texto plano, "
    "sin encabezados ni viñetas."
)

_MAX_TOKENS = 500

_RE_FENCE = re.compile(r"^```(?:\w+)?|```$", re.IGNORECASE | re.MULTILINE)
_RE_HTML = re.compile(r"<[^>]+>")


def _limpiar(texto: str) -> str:
    texto = _RE_FENCE.sub("", texto or "").strip()
    texto = _RE_HTML.sub("", texto)
    return texto.strip()


def resumir_actividad(*, proyecto, usuario=None) -> dict:
    """Resume la actividad de `proyecto`. Devuelve `{ok, resumen, error}`."""
    from lib.permisos import puede_ver_comentario

    partes: list[str] = [
        f"PROYECTO: {proyecto.codigo} «{proyecto.nombre}» — estado: {proyecto.get_estado_display()}"
    ]
    if (proyecto.descripcion or "").strip():
        partes.append("Descripción: " + proyecto.descripcion.strip()[:400])

    tareas = list(proyecto.tareas.select_related("asignada_a").order_by("estado", "-creado_en")[:40])
    if tareas:
        partes.append("TAREAS:")
        for t in tareas:
            asign = t.asignada_a.nombre_completo if getattr(t, "asignada_a_id", None) else "sin asignar"
            partes.append(f"- [{t.get_estado_display()}] {t.titulo} ({asign})")

    coments = [
        c for c in proyecto.comentarios.select_related("autor").order_by("-creado_en")[:30]
        if puede_ver_comentario(usuario, c)
    ]
    if coments:
        partes.append("COMENTARIOS (recientes primero):")
        for c in coments:
            autor = getattr(c.autor, "nombre_completo", "") or getattr(c.autor, "email", "")
            partes.append(f"- {c.creado_en:%Y-%m-%d} {autor}: {(c.cuerpo or '').strip()[:300]}")

    acts = list(proyecto.actividades.select_related("actor").all()[:40])
    if acts:
        partes.append("ACTIVIDAD:")
        for a in acts:
            partes.append(f"- {a.creado_en:%Y-%m-%d} {a.get_tipo_display()}: {a.descripcion}")

    if len(partes) == 1:
        partes.append("(Sin tareas, comentarios ni actividad registrada todavía.)")
    contexto_txt = "\n".join(partes)

    try:
        from chalanes.voz import preludio, reglas
        from lib.analistas import analizar
        from lib.sanear import sanear_contexto
        prompt = (preludio("comunicacion") + _SYSTEM + reglas() + "\n\n"
                  + sanear_contexto(contexto_txt, max_len=8000))
        res = analizar(estacion="comunicacion", prompt=prompt,
                       max_tokens=_MAX_TOKENS, temperatura=0.4,
                       actor_id=getattr(usuario, "pk", None))
    except Exception as exc:  # noqa: BLE001 — nunca tumbar la UI
        return {"ok": False, "resumen": "", "error": f"El Chalán no respondió: {str(exc)[:200]}"}

    resumen = _limpiar(res.texto)
    if not resumen:
        return {"ok": False, "resumen": "", "error": "El Chalán devolvió un resumen vacío."}
    return {"ok": True, "resumen": resumen, "error": ""}


__all__ = ["resumir_actividad"]
