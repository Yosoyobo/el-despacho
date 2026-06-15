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
    # S-Estados-Color-HEX: el chat de El Chalán se gatea por (chalan, usar).
    "chalan": "usar",
    # S-Checador: el item del sidebar aparece si el usuario puede checar.
    "checador": "checar",
    # V6 Bloque 7: Comunicaciones (Chalán correo + campañas).
    "comunicacion": "enviar_correo",
    # S-LC-Feedback-V10: áreas administrativas con gating granular delegable.
    "ajustes": "acceder",
    "directorio": "ver",
    "chalanes": "ver",
    "site": "ver",
    "catalogos": "estados",   # cualquier acción de catálogo enciende el grupo
    "interfono": "configurar",
    # los demás usan "ver"
}

MODULOS_VISIBLES = (
    "cartera", "proyectos", "pizarron", "buzon", "recados",
    "tesoreria", "contaduria", "catalogo", "cotizaciones",
    "facturacion", "chalan", "checador", "comunicacion",
    "directorio", "ajustes", "chalanes", "site",
    "catalogos", "interfono",
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


def sidebar_orden(request):
    """Orden del sidebar del Taller — global (super_admin) + override por usuario.

    S-LC-Feedback-V5 c6: orden global en `SidebarOrden`.
    S-LC-Feedback-V7: cada usuario acomoda el suyo en `SidebarOrdenUsuario`,
    que PISA la fila global para ese usuario. Inyecta
    `sidebar_orden` = `{slug: {orden, oculto}}`.
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"sidebar_orden": {}}
    try:
        from cuentas.models.sidebar_orden import SidebarOrden, SidebarOrdenUsuario
        mapa = {f.slug: {"orden": f.orden, "oculto": f.oculto, "grupo": ""} for f in SidebarOrden.objects.all()}
        for f in SidebarOrdenUsuario.objects.filter(usuario=user):
            # V9: el override del usuario también trae su carpeta/grupo.
            mapa[f.slug] = {"orden": f.orden, "oculto": f.oculto, "grupo": f.grupo}
        return {"sidebar_orden": mapa}
    except Exception:
        return {"sidebar_orden": {}}


def novedades_badge(request):
    """S-Chalanes-UX #5 — contador de novedades no vistas para el badge del
    sidebar (item Ayuda). Se acumula y se limpia al abrir /ayuda/novedades/."""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"novedades_no_vistas": 0}
    try:
        from lib import novedades as _nov
        return {"novedades_no_vistas": _nov.no_vistas_para(user)}
    except Exception:
        return {"novedades_no_vistas": 0}
