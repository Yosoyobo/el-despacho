"""Gating por permiso de las capacidades — compartido por el chat interno y el
servidor MCP. Doble guardrail: el prompt enumera solo lo permitido y aquí se
re-chequea antes de listar/ejecutar. `super_admin` es failsafe dentro de cada
helper de `lib.permisos` (regla §20)."""

from __future__ import annotations


def gate_ok(gating: str, usuario, modo: str = "lectura") -> bool:
    if gating == "abierto":
        return True
    if modo == "propuesta":
        # Las ESCRITURAS reusan el mapa de gating del catálogo del Dictado
        # (fuente única de la política de escritura — no se duplica aquí).
        from lib.dictado_catalogo import _gating_checks
        fn = _gating_checks().get(gating)
        return bool(fn(usuario)) if fn else False
    from lib import permisos
    fn = {
        "finanzas": permisos.puede_ver_finanzas,
        "cartera": permisos.puede_ver_cartera,
        "cotizaciones": permisos.puede_ver_cotizaciones,
        "facturacion": permisos.puede_ver_facturacion,
        "contaduria": permisos.puede_ver_contaduria,
        # LC #153: la acción canónica de lectura del catálogo es `ver_nombres`.
        "catalogo": lambda u: permisos.puede(u, "catalogo", "ver_nombres"),
    }.get(gating)
    return bool(fn(usuario)) if fn else False
