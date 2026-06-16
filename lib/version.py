"""Versión visible de El Despacho — fuente única de verdad.

Se muestra discreta en el footer de las 3 apps (Taller, Gerencia,
Recepción) vía el context processor `contexto_version`.

**Regla del proyecto:** actualizar `VERSION` y `VERSION_FECHA` en cada
sesión de trabajo que llegue a deploy. El esquema es semántico-ligero
`AÑO.MES.ITERACIÓN` (ej. `2026.06.3` = tercera entrega de junio 2026).
La fecha es legible para el usuario final; la versión es el ancla técnica.
"""

from __future__ import annotations

VERSION = "2026.06.53"
VERSION_FECHA = "15 de junio de 2026"


def contexto_version(request) -> dict:
    """Context processor: expone `app_version` y `app_version_fecha`.

    Registrar en `TEMPLATES.OPTIONS.context_processors` de los 3 settings.
    """
    return {
        "app_version": VERSION,
        "app_version_fecha": VERSION_FECHA,
    }


__all__ = ["VERSION", "VERSION_FECHA", "contexto_version"]
