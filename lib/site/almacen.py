"""Wrapper sobre la tabla `site_chequeo`. Vive aquí para que el cron, los
views y los tests usen la misma API.
"""

from __future__ import annotations

from typing import Any


def guardar(
    plataforma: str,
    estado: str,
    *,
    latencia_ms: int | None = None,
    mensaje_error: str | None = None,
    origen: str = "manual",
    actor_email: str | None = None,
):
    from apps.el_site.models import SiteChequeo
    return SiteChequeo.objects.create(
        plataforma=plataforma,
        estado=estado,
        latencia_ms=latencia_ms,
        mensaje_error=(mensaje_error or "")[:1000] or None,
        origen=origen,
        actor_email=actor_email,
    )


def ultimo_por_plataforma() -> dict[str, dict[str, Any]]:
    """Para cada plataforma del registry, retorna la lectura más reciente
    (de cualquier origen). Sirve para que la UI muestre estado cacheado
    sin re-chequear en vivo."""
    from apps.el_site.models import SiteChequeo

    from .registry import PLATAFORMAS

    out: dict[str, dict[str, Any]] = {}
    for plat in PLATAFORMAS:
        row = SiteChequeo.objects.filter(plataforma=plat).order_by("-probado_en").first()
        if row is None:
            out[plat] = {"estado": "sin_datos", "probado_en": None}
        else:
            out[plat] = {
                "estado": row.estado,
                "latencia_ms": row.latencia_ms,
                "mensaje_error": row.mensaje_error,
                "origen": row.origen,
                "probado_en": row.probado_en.isoformat(),
            }
    return out


def hay_integraciones_rojas() -> int:
    """Cantidad de plataformas cuya última lectura está en `error`. Usado por
    el badge del navbar."""
    return sum(1 for v in ultimo_por_plataforma().values() if v.get("estado") == "error")
