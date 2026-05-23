"""Context processors específicos del Taller (sidebar, etc)."""

from __future__ import annotations


def sidebar_grupos(request):
    """Marca qué grupos del sidebar están activos para auto-expandir.

    El template HTML no puede hacer fácilmente `'/x' in request.path` como
    boolean expression, así que lo precomputamos aquí.
    """
    path = getattr(request, "path", "") or ""
    return {
        "finanzas_grupo_activo": (
            "/tesoreria" in path
            or "/facturacion" in path
            or "/contaduria" in path
        ),
    }
