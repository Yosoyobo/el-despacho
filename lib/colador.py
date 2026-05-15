"""El Colador — sanea reportes de error y mensajes del Buzón antes de
persistirlos o exponerlos en UI.

Redacta patrones sensibles que aparecen típicamente en tracebacks Django o en
copias-pegadas que el usuario manda como reporte:

- Paths absolutos /data/, /opt/, /home/, /var/, /root/, /etc/
- API keys (sk-..., ghp_..., dop_v1_..., Bearer ..., strings 40+ chars sin
  espacios que parezcan tokens)
- Queries SQL crudas (heurística: contiene SELECT/INSERT/UPDATE/DELETE +
  FROM/INTO/SET)
- Direcciones IP — decisión de Oscar: SE REDACTAN por privacidad. Si un admin
  necesita el reporte crudo, lo lee directo de la tabla.

NO sanea: nombres de funciones, tipos de excepción, números de línea —
permanecen útiles para debugging.
"""

from __future__ import annotations

import re

_RE_PATH_SISTEMA = re.compile(
    r"(?<![\w/])/(?:data|opt|home|var|root|etc)(?:/[\w\-.@%]+)+",
    flags=re.IGNORECASE,
)
_RE_API_KEY_PREFIX = re.compile(
    r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|dop_v1_[A-Za-z0-9]{20,}"
    r"|Bearer\s+[A-Za-z0-9._\-]{20,})\b"
)
_RE_TOKEN_LARGO = re.compile(r"\b[A-Za-z0-9_\-]{40,}\b")
_RE_SQL = re.compile(
    r"\b(?:SELECT|INSERT|UPDATE|DELETE)\b[^\n]*\b(?:FROM|INTO|SET|WHERE)\b[^\n]*",
    flags=re.IGNORECASE,
)
_RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_IPV6 = re.compile(r"\b(?:[A-Fa-f0-9]{1,4}:){4,7}[A-Fa-f0-9]{1,4}\b")

# Hashes y digests de pruebas/git: dejarlos pasar si tienen 40 chars exactos.
# El umbral de _RE_TOKEN_LARGO es 40; lo reemplazamos solo si no es claramente
# un hash hexadecimal de 40 (sha1 git).
_RE_HASH_SHA1 = re.compile(r"\b[a-f0-9]{40}\b")


def colar_reporte(texto: str) -> str:
    """Aplica la lista de redacciones. Idempotente — pasar el resultado de
    nuevo a colar_reporte() no cambia nada."""
    if not isinstance(texto, str) or not texto:
        return ""
    out = _RE_API_KEY_PREFIX.sub("[REDACTED:api_key]", texto)
    out = _RE_PATH_SISTEMA.sub("[REDACTED:path]", out)
    out = _RE_SQL.sub("[REDACTED:sql]", out)
    out = _RE_IPV4.sub("[REDACTED:ip]", out)
    out = _RE_IPV6.sub("[REDACTED:ip]", out)
    # Tokens largos: solo si no son hashes git sha1 (40 chars hex). Hash queda.
    def _maybe_redact_token(m: re.Match) -> str:
        s = m.group(0)
        if _RE_HASH_SHA1.fullmatch(s):
            return s
        if s.startswith("[REDACTED"):
            return s
        return "[REDACTED:token]"
    out = _RE_TOKEN_LARGO.sub(_maybe_redact_token, out)
    return out
