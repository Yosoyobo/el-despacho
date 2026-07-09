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


def salud_sistema(request):
    """Badge ⚠️ global (LC 2026-07): si La Gerencia/El Site detecta una falla
    (token caído, Chalán en error), TODOS los usuarios del Taller la ven junto a
    Ajustes. Cacheado 60s; nunca tumba la UI."""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}
    try:
        from lib.salud_sistema import hay_falla
        r = hay_falla()
    except Exception:  # noqa: BLE001
        return {}
    return {"sistema_falla": r.get("falla", False), "sistema_falla_motivo": r.get("motivo", "")}
