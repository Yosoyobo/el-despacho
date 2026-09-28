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


def pestanas(request):
    """`embebido`: la página se está pintando DENTRO de una pestaña de El Taller.

    El navegador lo dice solo con `Sec-Fetch-Dest: iframe` en cada navegación del
    marco —también en las que el usuario hace dentro de la pestaña—, así que no
    hay que arrastrar un parámetro en cada enlace. Incrustada, la página no pinta
    menú, encabezado, banner ni pie: los pone el contenedor una sola vez (y así
    tampoco hay seis copias del banner sondeando cada 10 s).
    """
    return {"embebido": es_embebido(request)}


def es_embebido(request) -> bool:
    """El navegador lo dice con `Sec-Fetch-Dest: iframe`; cuando la página pasa
    por el service worker de la PWA esa cabecera llega como «empty», y el SW la
    repone como `X-Despacho-Marco: 1` (ver `interfono/sw_js.py`)."""
    headers = getattr(request, "headers", None)
    if not headers:
        return False
    return headers.get("Sec-Fetch-Dest") == "iframe" or headers.get("X-Despacho-Marco") == "1"


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
