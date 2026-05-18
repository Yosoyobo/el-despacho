"""Parser de tokens `@`, `#`, `$` en texto libre.

Regex: `(?<![A-Za-z0-9_])([@#$])([A-Za-z0-9_-]{1,80})`
La lookbehind evita falsos positivos en emails (`a@b.com`), hashtags como
parte de palabra, y `$50` (no inicia con letra). El sigil debe aparecer
después de espacio, inicio de string o puntuación.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_RE_REF = re.compile(r"(?<![A-Za-z0-9_])([@#$])([A-Za-z0-9_-]{1,80})")

_TIPO_POR_SIGIL = {"@": "usuario", "#": "proyecto", "$": "cliente"}


@dataclass(frozen=True)
class TokenRef:
    sigil: str           # '@' | '#' | '$'
    tipo: str            # 'usuario' | 'proyecto' | 'cliente'
    slug: str            # 'oscar' (sin sigil)
    token_original: str  # '@oscar' (con sigil)
    inicio: int          # offset en texto
    fin: int             # offset exclusivo


def extraer_tokens(texto: str) -> list[TokenRef]:
    """Devuelve la lista ordenada de tokens encontrados. No resuelve a entidades."""
    if not texto:
        return []
    tokens: list[TokenRef] = []
    for m in _RE_REF.finditer(texto):
        sigil = m.group(1)
        slug = m.group(2)
        # Rechaza slugs que terminan en `-` o solo dígitos al inicio (estilo `$50`
        # ya bloqueado por lookbehind, pero defensivo).
        if not slug or slug.endswith("-"):
            continue
        # `$50` puro numérico → no es referencia
        if sigil == "$" and slug.isdigit():
            continue
        tokens.append(TokenRef(
            sigil=sigil,
            tipo=_TIPO_POR_SIGIL[sigil],
            slug=slug.lower(),
            token_original=m.group(0),
            inicio=m.start(),
            fin=m.end(),
        ))
    return tokens
