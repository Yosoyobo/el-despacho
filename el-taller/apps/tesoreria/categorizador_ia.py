"""El Chalán sugiere el centro de costo de un gasto (estación `gastos`, S4).

Enumera los CentroDeCosto activos en el system prompt y pide al LLM elegir el
slug que mejor encaja con la descripción libre. Resuelve slug→pk validando
contra la tabla (NUNCA confía en el id/slug crudo del LLM). v1: solo centro de
costo (proveedor queda fuera para no inflar tokens).

Diseño defensivo: nunca lanza — devuelve `{ok, centro_de_costo_id,
centro_de_costo_nombre, confianza, error}`.
"""

from __future__ import annotations

import json
import re

_MAX_TOKENS = 150

_UMBRAL_CONFIANZA = 0.3


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


def sugerir_categoria(*, descripcion: str, usuario=None) -> dict:
    """Sugiere el centro de costo para `descripcion`."""
    from .models import CentroDeCosto

    descripcion = (descripcion or "").strip()
    if not descripcion:
        return {"ok": False, "error": "Escribe primero la descripción del gasto."}

    centros = list(CentroDeCosto.objects.filter(activo=True).order_by("nombre"))
    if not centros:
        return {"ok": False, "error": "No hay centros de costo configurados."}

    catalogo = "\n".join(
        f"- {c.slug}: {c.nombre}" + (f" — {c.descripcion}" if c.descripcion else "")
        for c in centros
    )
    system = (
        "Eres El Chalán contable de Learning Center. Te doy la descripción de un "
        "gasto y el catálogo de CENTROS DE COSTO. Elige el que mejor encaja.\n"
        "Responde SOLO JSON estricto, sin texto fuera:\n"
        '{"centro_de_costo_slug": "<slug-exacto-del-catálogo>"|null, "confianza": 0.0-1.0}\n'
        "Usa el slug EXACTO de la lista. Si ninguno encaja claramente, usa null y "
        "confianza<=0.3. No inventes slugs."
    )
    user = (
        f"CATÁLOGO DE CENTROS DE COSTO:\n{catalogo}\n\n"
        f"GASTO: {descripcion}\n\n¿Qué centro de costo le corresponde?"
    )

    try:
        from chalanes.voz import preludio, reglas
        from lib.analistas import analizar
        from lib.sanear import sanear_contexto
        prompt = preludio("gastos") + system + reglas() + "\n\n" + sanear_contexto(user, max_len=3000)
        res = analizar(estacion="gastos", prompt=prompt,
                       max_tokens=_MAX_TOKENS, temperatura=0.0,
                       actor_id=getattr(usuario, "pk", None))
    except Exception as exc:  # noqa: BLE001 — nunca tumbar la UI
        return {"ok": False, "error": f"El Chalán no respondió: {str(exc)[:200]}"}

    crudo = _parsear_json(res.texto)
    if crudo is None:
        return {"ok": False, "error": "El Chalán no devolvió una sugerencia legible."}

    slug = (crudo.get("centro_de_costo_slug") or "").strip()
    try:
        confianza = float(crudo.get("confianza") or 0)
    except (ValueError, TypeError):
        confianza = 0.0

    # Resolver slug→pk validando contra la tabla. Sin match o confianza baja →
    # no-match suave (el usuario elige a mano).
    centro = next((c for c in centros if c.slug == slug), None) if slug else None
    if centro is None or confianza <= _UMBRAL_CONFIANZA:
        return {"ok": True, "centro_de_costo_id": None,
                "centro_de_costo_nombre": "", "confianza": confianza, "error": ""}

    return {"ok": True, "centro_de_costo_id": centro.pk,
            "centro_de_costo_nombre": centro.nombre, "confianza": confianza, "error": ""}


__all__ = ["sugerir_categoria"]
