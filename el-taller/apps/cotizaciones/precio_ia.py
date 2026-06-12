"""El Chalán sugiere un rango de precio para un servicio (estación `precio`, S4).

Toma el Servicio (precio_base, costo) + el histórico de `CotizacionItem` de ese
servicio en cotizaciones no anuladas, y pide al LLM un rango realista. Las
estadísticas (min/max/avg del histórico) se calculan en Python y se pasan como
grounding al prompt.

Diseño defensivo: nunca lanza — devuelve `{ok, precio_minimo, precio_maximo,
justificacion, confianza, n_historico, error}`.
"""

from __future__ import annotations

import json
import re

_SYSTEM = (
    "Eres El Chalán de pricing de Learning Center, un despacho mexicano de "
    "diseño y maquila B2B. Te doy un producto/servicio (precio_base, costo) y el "
    "histórico de precios unitarios cobrados en cotizaciones pasadas. Sugiere un "
    "RANGO de precio unitario realista para una nueva cotización.\n"
    "REGLAS:\n"
    "1. Responde SOLO JSON estricto, sin texto fuera:\n"
    '   {"precio_minimo": número, "precio_maximo": número, '
    '"justificacion": "frase corta en español", "confianza": 0.0-1.0}\n'
    "2. NUNCA sugieras un precio por debajo del costo (respeta el margen).\n"
    "3. Si hay histórico, mantente cerca de él; si no, parte del precio_base.\n"
    "4. No inventes datos que no estén en el contexto. Sé conciso."
)

_MAX_TOKENS = 300


def _a_float(valor):
    if valor in (None, ""):
        return None
    try:
        return round(float(str(valor).replace(",", "").replace("$", "").strip()), 2)
    except (ValueError, TypeError):
        return None


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


def sugerir_precio(*, servicio_id, usuario) -> dict:
    """Sugiere `{precio_minimo, precio_maximo}` para `servicio_id`."""
    from apps.el_catalogo.models import Servicio

    from .models import CotizacionItem

    try:
        servicio = Servicio.objects.get(pk=servicio_id)
    except (Servicio.DoesNotExist, ValueError, TypeError):
        return {"ok": False, "error": "Producto no encontrado."}

    historico = list(
        CotizacionItem.objects
        .filter(servicio_id=servicio.pk)
        .exclude(cotizacion__estado="anulada")
        .select_related("cotizacion")
        .order_by("-cotizacion__creado_en")[:20]
    )
    precios = [float(it.precio_unitario) for it in historico if it.precio_unitario]
    n = len(precios)
    stats_txt = "(sin histórico)"
    if precios:
        stats_txt = (
            f"min={min(precios):.2f} · max={max(precios):.2f} · "
            f"promedio={sum(precios) / n:.2f} · n={n} (precios recientes: "
            + ", ".join(f"{p:.2f}" for p in precios[:8]) + ")"
        )

    user_prompt = (
        f"PRODUCTO: {servicio.nombre}\n"
        f"precio_base: {servicio.precio_base}\n"
        f"costo: {servicio.costo}\n"
        f"HISTÓRICO de precios cobrados: {stats_txt}\n"
        "Sugiere el rango de precio unitario."
    )

    try:
        from chalanes.voz import preludio, reglas
        from lib.analistas import analizar
        from lib.sanear import sanear_contexto
        prompt = (preludio("precio") + _SYSTEM + reglas() + "\n\n"
                  + sanear_contexto(user_prompt, max_len=2000))
        res = analizar(estacion="precio", prompt=prompt,
                       max_tokens=_MAX_TOKENS, temperatura=0.3,
                       actor_id=getattr(usuario, "pk", None))
    except Exception as exc:  # noqa: BLE001 — nunca tumbar la UI
        return {"ok": False, "error": f"El Chalán no respondió: {str(exc)[:200]}"}

    crudo = _parsear_json(res.texto)
    if crudo is None:
        return {"ok": False, "error": "El Chalán no devolvió un rango legible."}

    pmin = _a_float(crudo.get("precio_minimo"))
    pmax = _a_float(crudo.get("precio_maximo"))
    if pmin is None and pmax is None:
        return {"ok": False, "error": "El Chalán no devolvió precios."}
    # Normaliza: si solo vino uno, úsalo para ambos; ordena min<=max.
    if pmin is None:
        pmin = pmax
    if pmax is None:
        pmax = pmin
    if pmin > pmax:
        pmin, pmax = pmax, pmin
    try:
        confianza = float(crudo.get("confianza") or 0)
    except (ValueError, TypeError):
        confianza = 0.0

    return {
        "ok": True,
        "precio_minimo": pmin,
        "precio_maximo": pmax,
        "justificacion": str(crudo.get("justificacion") or "")[:300],
        "confianza": confianza,
        "n_historico": n,
        "error": "",
    }


__all__ = ["sugerir_precio"]
