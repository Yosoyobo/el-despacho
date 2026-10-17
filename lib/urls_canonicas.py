"""URLs canónicas de El Despacho: un solo lugar que sabe cuál es «la casa».

El dominio viejo `*.ninomeando.com` se reemplazó por `*.learningcenter.mx` el
2026-06-07, pero hay cosas que sobreviven al cambio: suscripciones push que el
navegador registró estando en el dominio viejo (su service worker abre las rutas
relativas **en su propio origen**), URLs absolutas guardadas en base y un
`TALLER_URL` heredado en algún `.env`. Todo lo que arme o abra un enlace
absoluto pasa por aquí.

Sin dependencias de Django en el import (lib/ es «NO-Django»); `settings` se lee
perezosamente.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit, urlunsplit

# sufijo viejo → sufijo vigente. Agregar otro dominio retirado es una línea.
DOMINIOS_HEREDADOS: dict[str, str] = {"ninomeando.com": "learningcenter.mx"}

TALLER_URL_DEFAULT = "https://taller.learningcenter.mx/"

_ABSOLUTA = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def host_canonico(host: str) -> str:
    """`taller.ninomeando.com` → `taller.learningcenter.mx`; lo demás, igual."""
    h = (host or "").lower()
    for viejo, nuevo in DOMINIOS_HEREDADOS.items():
        if h == viejo:
            return nuevo
        if h.endswith("." + viejo):
            return h[: -len(viejo)] + nuevo
    return host


def es_host_heredado(host: str) -> bool:
    h = (host or "").lower()
    return any(h == v or h.endswith("." + v) for v in DOMINIOS_HEREDADOS)


def normalizar_url_heredada(url: str) -> str:
    """Si `url` es absoluta y apunta al dominio viejo, la lleva al vigente
    (mismo esquema, ruta, query y ancla). Rutas relativas y otros hosts: igual."""
    if not url or not _ABSOLUTA.match(url):
        return url
    partes = urlsplit(url)
    if not es_host_heredado(partes.hostname or ""):
        return url
    puerto = f":{partes.port}" if partes.port else ""
    return urlunsplit(
        (partes.scheme, host_canonico(partes.hostname or "") + puerto,
         partes.path, partes.query, partes.fragment)
    )


def origen_taller() -> str:
    """`https://taller.learningcenter.mx` (sin barra final), ya normalizado."""
    base = TALLER_URL_DEFAULT
    try:
        from django.conf import settings
        base = getattr(settings, "TALLER_URL", "") or os.environ.get("TALLER_URL", "") or base
    except Exception:  # noqa: BLE001 — sin Django configurado: el default
        base = os.environ.get("TALLER_URL", "") or base
    return normalizar_url_heredada(base).rstrip("/")


def url_absoluta_taller(url: str) -> str:
    """Ruta relativa → absoluta contra El Taller; absoluta → sólo normalizada.

    Es la URL que viaja en el payload de un push: aunque el service worker que
    la reciba sea uno viejo, registrado en otro origen, `openWindow` con una URL
    absoluta abre El Taller de verdad.
    """
    if not url:
        return url
    if _ABSOLUTA.match(url):
        return normalizar_url_heredada(url)
    if url.startswith("//"):
        return url
    return origen_taller() + (url if url.startswith("/") else "/" + url)
