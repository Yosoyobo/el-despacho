"""Saneamiento de contexto para input de usuario antes de mostrarlo o almacenarlo
en campos sensibles (descripciones de tickets, comentarios, etc).

No reemplaza el escaping de Django templates (que es la última línea de defensa);
esta función es para neutralizar payloads obvios antes de pasarlos a IA o webhooks,
donde el escaping HTML no aplica.
"""

from __future__ import annotations

import html
import re

_RE_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RE_SCRIPT = re.compile(r"<\s*/?\s*(script|iframe|object|embed|link|meta)[^>]*>", re.IGNORECASE)
_RE_JS_PROTO = re.compile(r"javascript\s*:", re.IGNORECASE)
_RE_ON_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)


def sanear_contexto(texto: str, *, max_len: int = 10_000) -> str:
    """Limpia un string de payloads obvios manteniendo legibilidad humana."""
    if not isinstance(texto, str):
        return ""
    if not texto:
        return ""
    out = _RE_CTRL.sub("", texto)
    out = _RE_SCRIPT.sub("", out)
    out = _RE_JS_PROTO.sub("", out)
    out = _RE_ON_HANDLER.sub(" ", out)
    out = html.escape(out, quote=False)
    out = out.strip()
    if len(out) > max_len:
        out = out[:max_len].rstrip() + "…"
    return out
