"""Context processors de cuentas.

`permisos_modulos`: inyecta dict {modulo: bool} con `puede(user, modulo, "ver")`
para usar como `{% if permisos_modulos.cartera %}` en el sidebar y otros
componentes condicionales. Una sola query a `PermisoUsuario` por request
(vía la cache interna de `_puede` — cada lookup hace `.exists()`, podríamos
optimizar a una sola query luego si se vuelve cuello de botella).
"""

from __future__ import annotations

from lib.permisos import puede as _puede

# Mapa de módulo → acción que se evalúa para decidir si el item del
# sidebar aparece. Default es "ver"; los módulos que usan otra acción
# (porque no tienen "ver" en sus defaults) la declaran aquí.
ACCION_VISIBLE_POR_MODULO = {
    "buzon": "ver_propios",        # admin lo ve por ver_propios también
    "catalogo": "ver_nombres",
    # S-LC-Feedback-V5 c5: acceso a Gerencia heredable por permiso granular.
    "gerencia": "acceder",
    # los demás usan "ver"
}

MODULOS_VISIBLES = (
    "cartera", "proyectos", "pizarron", "buzon", "recados",
    "tesoreria", "contaduria", "catalogo", "cotizaciones",
    "facturacion",
    "directorio", "ajustes", "chalanes", "site",
    "centros_costo", "tasas",
    "gerencia",
)


def permisos_modulos(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"permisos_modulos": {}}
    accesos = {}
    for m in MODULOS_VISIBLES:
        accion = ACCION_VISIBLE_POR_MODULO.get(m, "ver")
        accesos[m] = _puede(user, m, accion)
    return {"permisos_modulos": accesos}
