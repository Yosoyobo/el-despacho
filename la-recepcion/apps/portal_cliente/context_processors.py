"""Lo que toda plantilla de La Recepción necesita saber: quién entró."""

from __future__ import annotations


def portal(request):
    acceso = getattr(request, "acceso", None)
    documentos = False
    if acceso is not None:
        try:
            from portal.models import ConfiguracionPortal

            documentos = ConfiguracionPortal.obtener().documentos_activo
        except Exception:  # noqa: BLE001
            documentos = False
    return {
        "acceso_portal": acceso,
        "cliente_portal": getattr(request, "cliente", None),
        "documentos_portal": documentos,
    }
