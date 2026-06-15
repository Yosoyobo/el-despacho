"""Formato de hora por usuario (S-LC-Feedback-V11).

Cada usuario elige cómo ver TODAS las horas de la plataforma: 24h (default) o
AM/PM. El filtro de plantilla `hfmt` (cuentas.templatetags.horas) reformatea
cualquier formato de fecha de Django respetando esa preferencia, leyéndola de
un thread-local que el context processor `formato_hora` fija por request.

Diseño: el context processor corre al armar el RequestContext (antes de
renderizar los nodos), así que el thread-local ya está puesto cuando los
filtros se evalúan. Fuera de un request (comandos, workers) cae a 24h.
"""

from __future__ import annotations

import threading

_local = threading.local()

# Tokens de HORA de Django que convertimos a 12h cuando el usuario pide AM/PM.
# Usamos `a` (a.m./p.m. en minúsculas con puntos) por ser lo natural en español.
_REEMPLAZOS_AMPM = (
    ("H:i:s", "g:i:s a"),
    ("H:i", "g:i a"),
    ("G:i", "g:i a"),
)


def set_formato(pref: str) -> None:
    _local.pref = pref if pref in ("24h", "ampm") else "24h"


def get_formato() -> str:
    return getattr(_local, "pref", "24h")


def aplicar(fmt: str, pref: str | None = None) -> str:
    """Devuelve `fmt` con los tokens de hora ajustados a la preferencia.

    Solo toca la porción de HORA: las partes de fecha (Y-m-d, D j N, etc.)
    quedan intactas, así `"Y-m-d H:i"` → `"Y-m-d g:i a"` en modo AM/PM.
    """
    pref = pref or get_formato()
    if pref != "ampm" or not fmt:
        return fmt
    for token, reemplazo in _REEMPLAZOS_AMPM:
        if token in fmt:
            fmt = fmt.replace(token, reemplazo)
    return fmt
