"""Helpers de plantilla de El Checador — mapa OpenStreetMap embebido.

OSM no requiere API key ni costo; el iframe se muestra siempre dentro de un
modal (decisión Oscar, S-Checador-V1.2). `osm_embed_src` arma el `bbox` (un
cuadro de ~250 m alrededor del punto) + el marcador; `osm_link` da el enlace
para "abrir en mapa" en otra pestaña.
"""

from __future__ import annotations

from django import template

register = template.Library()

# Medio lado del cuadro en grados (~250 m). Suficiente para ubicar la checada.
_DELTA = 0.0025


def _coords(lat, lng):
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None


@register.simple_tag
def osm_embed_src(lat, lng) -> str:
    c = _coords(lat, lng)
    if c is None:
        return ""
    la, lo = c
    bbox = f"{lo - _DELTA},{la - _DELTA},{lo + _DELTA},{la + _DELTA}"
    return (
        "https://www.openstreetmap.org/export/embed.html"
        f"?bbox={bbox}&layer=mapnik&marker={la},{lo}"
    )


@register.simple_tag
def osm_link(lat, lng) -> str:
    c = _coords(lat, lng)
    if c is None:
        return ""
    la, lo = c
    return f"https://www.openstreetmap.org/?mlat={la}&mlon={lo}#map=17/{la}/{lo}"


@register.simple_tag
def gmaps_link(lat, lng) -> str:
    """Enlace a Google Maps centrado en el punto con un pin."""
    c = _coords(lat, lng)
    if c is None:
        return ""
    la, lo = c
    return f"https://www.google.com/maps/search/?api=1&query={la},{lo}"


@register.simple_tag
def gmaps_dir_link(lat, lng) -> str:
    """Enlace de NAVEGACIÓN ("Cómo llegar") en Google Maps hacia el punto."""
    c = _coords(lat, lng)
    if c is None:
        return ""
    la, lo = c
    return f"https://www.google.com/maps/dir/?api=1&destination={la},{lo}"
