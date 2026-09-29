"""Lo que toda plantilla de La Recepción necesita saber: quién entró."""

from __future__ import annotations


def portal(request):
    acceso = getattr(request, "acceso", None)
    return {
        "acceso_portal": acceso,
        "cliente_portal": getattr(request, "cliente", None),
    }
