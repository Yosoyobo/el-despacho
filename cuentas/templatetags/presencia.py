"""`{% actividad_de usuario as act %}` — la presencia de una persona, para pintar.

Devuelve lo que arma `lib.presencia.describir`, o **None si quien mira no tiene
el permiso `(equipo, ver_actividad)`** (§4 #20). Las plantillas hacen
`{% include "_componentes_tailadmin/_presencia.html" with act=act %}` y el partial
no pinta nada con None: así el permiso se respeta en un solo lugar y no en cada
pantalla.

Los nombres de los objetos que ya se buscaron se recuerdan en la petición, así
una lista de diez personas en el mismo proyecto no lo busca diez veces.
"""

from __future__ import annotations

import contextlib

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def actividad_de(context, usuario):
    request = context.get("request")
    viewer = getattr(request, "user", None) if request is not None else None
    if usuario is None or viewer is None:
        return None
    try:
        from lib import presencia
        from lib.permisos import puede_ver_actividad_equipo

        if not puede_ver_actividad_equipo(viewer):
            return None
        memo = getattr(request, "_presencia_memo", None)
        if memo is None:
            memo = {}
            with contextlib.suppress(Exception):
                request._presencia_memo = memo
        return presencia.describir(usuario, viewer=viewer, memo=memo)
    except Exception:  # noqa: BLE001 — una ficha no se cae por la presencia
        return None
