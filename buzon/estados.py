"""Helpers de lectura de los estados del Buzón (S-Buzon-Estados-V1).

Módulo plano (sin Django views) para que vistas, forms y templatetags
compartan la misma fuente de label/color/lista de estados, con cache de
proceso (60s) que evita N+1 en listas con muchos badges.
"""

from __future__ import annotations

from buzon.models.estado import ESTADOS_BASE

_CACHE_CLAVE = "buzon:mapa_estados:v1"

# Fallback cuando la DB no está migrada (tests aislados, primer boot).
_FALLBACK_LABEL = {slug: label for slug, label, *_ in ESTADOS_BASE}
_FALLBACK_COLOR = {slug: color for slug, _label, color, *_ in ESTADOS_BASE}


def _mapa() -> dict:
    """slug → {label, color, activo, orden, terminal}. Cache 60s."""
    from django.core.cache import cache

    cacheado = cache.get(_CACHE_CLAVE)
    if cacheado is not None:
        return cacheado
    from buzon.models.estado import EstadoBuzon

    try:
        mapa = {
            e.slug: {
                "label": e.label, "color": e.color, "activo": e.activo,
                "orden": e.orden, "terminal": e.terminal, "accion": e.accion,
            }
            for e in EstadoBuzon.objects.all()
        }
        cache.set(_CACHE_CLAVE, mapa, 60)
        return mapa
    except Exception:  # noqa: BLE001 — DB sin migrar
        return {}


def invalidar_cache() -> None:
    """Llamado desde signals al guardar/borrar un EstadoBuzon."""
    from django.core.cache import cache

    cache.delete(_CACHE_CLAVE)


def label_de(slug: str) -> str:
    info = _mapa().get(slug)
    if info:
        return info["label"]
    return _FALLBACK_LABEL.get(slug, (slug or "").replace("_", " ").capitalize())


def color_de(slug: str) -> str:
    info = _mapa().get(slug)
    if info:
        return info["color"]
    return _FALLBACK_COLOR.get(slug, "#667085")


def accion_de(slug: str) -> str:
    """Acción automática configurada para el estado (o 'ninguna')."""
    info = _mapa().get(slug)
    return (info or {}).get("accion", "ninguna")


def estados_activos() -> list[dict]:
    """Lista [{slug, label, color}] de estados activos, ordenados. Para
    poblar dropdowns de filtro y el selector de estado del form de respuesta."""
    mapa = _mapa()
    if mapa:
        activos = [
            {"slug": slug, "label": v["label"], "color": v["color"], "orden": v["orden"]}
            for slug, v in mapa.items() if v["activo"]
        ]
        activos.sort(key=lambda x: (x["orden"], x["label"]))
        return [{"slug": a["slug"], "label": a["label"], "color": a["color"]} for a in activos]
    # Fallback sin DB: los 4 base.
    return [{"slug": s, "label": label_de(s), "color": color_de(s)}
            for s, *_ in ESTADOS_BASE]
