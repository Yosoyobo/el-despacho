"""El Chalán redacta/mejora plantillas de correo (estación `correo_redaccion`).

Dado una intención en lenguaje natural + el HTML actual + las variables
permitidas, devuelve HTML nuevo para el CUERPO del correo. Reglas duras:
preservar las variables `{{ }}` tal cual, estilos inline, sin <script>, sin
wrapper <html>/<head>. Diseño defensivo: nunca lanza — `{ok, html, error}`.
"""

from __future__ import annotations

import re

_SYSTEM = """\
Eres El Chalán de Learning Center. Redactas el CUERPO HTML de un correo
profesional en español para un despacho de diseño/maquila B2B.

REGLAS ESTRICTAS:
1. Devuelve SOLO HTML del cuerpo (sin ```), sin etiquetas <html>, <head>,
   <body>, <script> ni <style> con JS. Usa estilos INLINE (style="...").
2. PRESERVA EXACTAMENTE las variables entre dobles llaves que te den
   (ej. {{ codigo }}, {{ total }}). No las traduzcas ni inventes otras.
3. Tono cordial y profesional. Conciso. Español de México.
4. No incluyas asunto ni encabezados de correo; solo el cuerpo.
"""

_RE_SCRIPT = re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL)
_RE_FENCE = re.compile(r"^```(?:html)?|```$", re.IGNORECASE | re.MULTILINE)


def _limpiar(html: str) -> str:
    html = _RE_FENCE.sub("", html or "").strip()
    html = _RE_SCRIPT.sub("", html)
    return html.strip()


def redactar(*, intencion: str, html_actual: str = "", variables: list[str] | None = None,
             usuario=None) -> dict:
    """Genera/mejora el HTML del cuerpo. Devuelve `{ok, html, error}`."""
    intencion = (intencion or "").strip()
    if not intencion:
        return {"ok": False, "html": "", "error": "Escribe qué quieres que haga El Chalán."}

    vars_txt = ", ".join(f"{{{{ {v} }}}}" for v in (variables or [])) or "(ninguna)"
    partes = [
        f"VARIABLES PERMITIDAS (presérvalas tal cual): {vars_txt}",
        "",
        "HTML ACTUAL DEL CORREO:",
        (html_actual or "(vacío — créalo desde cero)"),
        "",
        f"LO QUE QUIERE EL USUARIO:\n{intencion}",
        "",
        "Devuelve el nuevo cuerpo HTML completo.",
    ]
    user_prompt = "\n".join(partes)

    try:
        from chalanes.voz import preludio
        from lib.analistas import analizar
        from lib.sanear import sanear_contexto
        prompt = preludio("correo_redaccion") + _SYSTEM + "\n\n" + sanear_contexto(user_prompt, max_len=8000)
        res = analizar(estacion="correo_redaccion", prompt=prompt,
                       max_tokens=1500, temperatura=0.4,
                       actor_id=getattr(usuario, "pk", None))
    except Exception as exc:  # noqa: BLE001 — nunca tumbar la UI
        return {"ok": False, "html": "", "error": f"El Chalán no respondió: {exc}"}

    html = _limpiar(res.texto)
    if not html:
        return {"ok": False, "html": "", "error": "El Chalán devolvió un resultado vacío."}
    return {"ok": True, "html": html, "error": ""}


__all__ = ["redactar"]
