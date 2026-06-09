"""Helpers de lectura de los tipos del Buzón (S-LC-Buzon-V2).

Espejo de buzon.estados: fuente única de label/color/lista de tipos, con
cache de proceso (60s) para evitar N+1 en listas. Invalida desde signal al
guardar/borrar un TipoBuzon.
"""

from __future__ import annotations

from buzon.models.tipo import TIPOS_BASE

_CACHE_CLAVE = "buzon:mapa_tipos:v1"

_FALLBACK_LABEL = {slug: label for slug, label, *_ in TIPOS_BASE}
_FALLBACK_COLOR = {slug: color for slug, _label, color, *_ in TIPOS_BASE}


def _mapa() -> dict:
    """slug → {label, color, activo, orden}. Cache 60s."""
    from django.core.cache import cache

    cacheado = cache.get(_CACHE_CLAVE)
    if cacheado is not None:
        return cacheado
    from buzon.models.tipo import TipoBuzon

    try:
        mapa = {
            t.slug: {"label": t.label, "color": t.color, "activo": t.activo, "orden": t.orden}
            for t in TipoBuzon.objects.all()
        }
        cache.set(_CACHE_CLAVE, mapa, 60)
        return mapa
    except Exception:  # noqa: BLE001 — DB sin migrar
        return {}


def invalidar_cache() -> None:
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


def tipos_activos() -> list[dict]:
    """Lista [{slug, label, color}] de tipos activos, ordenados. Para poblar
    el selector del form de nuevo mensaje y los chips de filtro."""
    mapa = _mapa()
    if mapa:
        activos = [
            {"slug": slug, "label": v["label"], "color": v["color"], "orden": v["orden"]}
            for slug, v in mapa.items() if v["activo"]
        ]
        activos.sort(key=lambda x: (x["orden"], x["label"]))
        return [{"slug": a["slug"], "label": a["label"], "color": a["color"]} for a in activos]
    return [{"slug": s, "label": label_de(s), "color": color_de(s)} for s, *_ in TIPOS_BASE]
