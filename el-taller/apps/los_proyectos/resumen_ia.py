"""El Chalán resume la actividad de un proyecto (estación `comunicacion`, S4).

Junta los PRODUCTOS involucrados + el feed de `ActividadProyecto` + comentarios
visibles (respetando `es_interno`) + tareas con su estado, y pide al LLM un
resumen ejecutivo. NO se persiste — se muestra en un modal HTMX. Diseño
defensivo: nunca lanza — devuelve `{ok, resumen, error}`.

LC 2026-08-04 (Oscar): «debe tener el estilo actualizado, resumido, claro y
conciso, y tomar en cuenta los productos involucrados». Así que el formato deja
de ser un párrafo corrido y pasa a renglones cortos «Etiqueta: valor» —el mismo
estilo con el que ahora contesta el chat— y los productos entran al contexto.
"""

from __future__ import annotations

import re

_SYSTEM = (
    "Eres El Chalán de Learning Center, un despacho mexicano de diseño y maquila. "
    "Te doy un proyecto con sus productos, tareas, comentarios y actividad. "
    "Devuelve un resumen EJECUTIVO Y CORTO en español de México, con este formato "
    "exacto, un renglón por línea y sin markdown:\n"
    "Estado: <estado actual> · <cliente>\n"
    "Productos: <qué se está produciendo, con cantidades si las hay>\n"
    "Avance: <una frase de lo que ya se hizo>\n"
    "Pendiente: <una frase de lo que falta; si no hay nada abierto, dilo>\n"
    "Atención: <una frase SOLO si hay algo atrasado, bloqueado o en riesgo; si no, "
    "omite este renglón>\n"
    "Reglas: máximo 5 renglones, ninguno de más de 25 palabras, usa SOLO los datos "
    "dados y no inventes nada. Nada de encabezados, viñetas ni asteriscos."
)

_MAX_TOKENS = 400

_RE_FENCE = re.compile(r"^```(?:\w+)?|```$", re.IGNORECASE | re.MULTILINE)
_RE_HTML = re.compile(r"<[^>]+>")
_RE_ENFASIS = re.compile(r"(\*\*|__)(.+?)\1", re.DOTALL)


def _limpiar(texto: str) -> str:
    texto = _RE_FENCE.sub("", texto or "").strip()
    texto = _RE_HTML.sub("", texto)
    return _RE_ENFASIS.sub(r"\2", texto).strip()


def resumir_actividad(*, proyecto, usuario=None) -> dict:
    """Resume la actividad de `proyecto`. Devuelve `{ok, resumen, error}`."""
    from lib.permisos import puede_ver_comentario

    cliente = getattr(getattr(proyecto, "cliente", None), "razon_social", "") or "sin cliente"
    partes: list[str] = [
        f"PROYECTO: {proyecto.codigo} «{proyecto.nombre}» — cliente: {cliente} — "
        f"estado: {proyecto.get_estado_display()}"
    ]
    if (proyecto.descripcion or "").strip():
        partes.append("Descripción: " + proyecto.descripcion.strip()[:400])

    # LC 2026-08-04 (Oscar): el resumen tiene que tomar en cuenta lo que se está
    # produciendo. El alias del proyecto manda sobre el nombre del catálogo.
    try:
        lineas_producto = list(proyecto.productos_incluidos)
    except Exception:  # noqa: BLE001 — un producto raro no tumba el resumen
        lineas_producto = []
    if lineas_producto:
        partes.append("PRODUCTOS INVOLUCRADOS:")
        for pp in lineas_producto[:20]:
            cantidad = getattr(pp, "cantidad", None)
            merma = getattr(pp, "merma", 0) or 0
            extra = f" (+{merma} de merma)" if merma else ""
            partes.append(
                f"- {pp.nombre_visible}"
                + (f" · {cantidad} pz{extra}" if cantidad else "")
            )

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
