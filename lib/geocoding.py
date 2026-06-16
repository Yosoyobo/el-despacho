"""Geocoding gratis vía Nominatim (OpenStreetMap) — S-Mandados-V2.

Regla del proyecto "gratis o abortamos": Nominatim es la única vía sin costo
recurrente para buscar direcciones e identificar POIs. Su política de uso pide:
- `User-Agent` identificable (lo mandamos),
- no abusar (cacheamos por consulta y el front hace *debounce*, no por tecla),
- atribución a OpenStreetMap (la pone el mapa Leaflet).

Todo es DEFENSIVO: si Nominatim cae, da timeout o responde basura, devolvemos
`[]` / `{}` y la UI sigue funcionando con la captura manual del pin.
"""

from __future__ import annotations

import contextlib

_BASE = "https://nominatim.openstreetmap.org"
_UA = "El Despacho - Learning Center (NoKo Devs; contacto@noko.mx)"
_TIMEOUT = 6.0
_CACHE_TTL = 3600  # 1 h por consulta


def _cache():
    with contextlib.suppress(Exception):
        from django.core.cache import cache
        return cache
    return None


def buscar(texto: str, limite: int = 6) -> list[dict]:
    """Busca direcciones/POIs por texto libre. Devuelve una lista de
    `{nombre, direccion, lat, lng, tipo}` (vacía si falla o el texto es corto)."""
    texto = (texto or "").strip()
    if len(texto) < 4:
        return []
    ckey = f"geocode:buscar:{limite}:{texto.lower()}"
    c = _cache()
    if c is not None:
        cached = c.get(ckey)
        if cached is not None:
            return cached

    resultados: list[dict] = []
    try:
        import httpx
        resp = httpx.get(
            f"{_BASE}/search",
            params={
                "q": texto,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": max(1, min(limite, 10)),
                "countrycodes": "mx",
                "accept-language": "es",
            },
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            for item in resp.json():
                lat = item.get("lat")
                lon = item.get("lon")
                if lat is None or lon is None:
                    continue
                nombre = item.get("name") or (item.get("display_name") or "").split(",")[0]
                resultados.append({
                    "nombre": (nombre or "").strip()[:120],
                    "direccion": (item.get("display_name") or "").strip()[:240],
                    "lat": float(lat),
                    "lng": float(lon),
                    "tipo": item.get("type") or item.get("category") or "",
                })
    except Exception:  # noqa: BLE001 — nunca tumba la operación
        return []

    if c is not None:
        with contextlib.suppress(Exception):
            c.set(ckey, resultados, _CACHE_TTL)
    return resultados


def identificar(lat, lng) -> dict:
    """Reverse geocode: identifica el nombre/dirección de un punto (al picar el
    mapa). Devuelve `{nombre, direccion}` o `{}` si falla."""
    try:
        la = float(lat)
        lo = float(lng)
    except (TypeError, ValueError):
        return {}
    ckey = f"geocode:rev:{round(la, 5)}:{round(lo, 5)}"
    c = _cache()
    if c is not None:
        cached = c.get(ckey)
        if cached is not None:
            return cached

    out: dict = {}
    try:
        import httpx
        resp = httpx.get(
            f"{_BASE}/reverse",
            params={
                "lat": la, "lon": lo, "format": "jsonv2",
                "accept-language": "es", "zoom": 18,
            },
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            nombre = data.get("name") or (data.get("display_name") or "").split(",")[0]
            out = {
                "nombre": (nombre or "").strip()[:120],
                "direccion": (data.get("display_name") or "").strip()[:240],
            }
    except Exception:  # noqa: BLE001
        return {}

    if c is not None and out:
        with contextlib.suppress(Exception):
            c.set(ckey, out, _CACHE_TTL)
    return out


def primer_resultado(texto: str) -> dict | None:
    """Conveniencia para El Chalán: la mejor coincidencia de `buscar`, o None."""
    res = buscar(texto, limite=1)
    return res[0] if res else None
