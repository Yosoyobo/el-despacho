"""Defaults de PermisoUsuario por rol.

Compilado de:
- DOC_01 §4.4 (autocomplete por rol — implícito en views.py)
- DOC_03 §5.1 (Los Recados — bandeja, crear, adjuntar, editar)
- DOC_04 §5 (El Dictado — crear_proyecto, etc.)
- DOC_06 §11 (La Tesorería — capturar, ocr, anular, reportes)

La migración 0007 seedea filas con `activo=True` para cada (modulo, permiso)
listado en el rol del usuario.
"""

from __future__ import annotations

# Acciones por módulo — espejo "todo permitido" para super_admin y dueno.
TODO_CARTERA = ["ver", "crear", "editar", "archivar"]
TODO_PROYECTOS = ["ver", "crear", "editar", "asignar", "cambiar_estado"]
TODO_PIZARRON = ["ver", "crear", "editar", "completar", "ver_internos"]
TODO_BUZON = ["ver_propios", "ver_todos", "responder"]
TODO_RECADOS = ["ver", "crear", "editar_propios", "adjuntar_drive", "ver_historial_todos"]
TODO_TESORERIA = [
    "ver", "capturar_ingreso", "capturar_egreso", "ocr",
    "dictado_gasto", "anular", "reportes", "exportar",
]
TODO_DICTADO = ["crear_proyecto", "actualizar_proyecto", "crear_tarea", "registrar_ingreso", "registrar_egreso"]
TODO_CONTADURIA = ["ver", "capturar", "anular", "reportes"]
# Pre-S2b.2: el Catálogo se mudó a El Taller con 7 permisos toggleables
# individualmente por super_admin desde /directorio/<id>/permisos/.
TODO_CATALOGO = [
    "ver_nombres", "ver_precios", "crear", "editar", "editar_precios",
    "archivar", "gestionar_categorias",
]
# S2b.cotizaciones-v1: Las Cotizaciones. Aprobar/rechazar/anular son del jefe;
# el contador puede armar y enviar pero no cerrar el ciclo.
TODO_COTIZACIONES = ["ver", "crear", "editar", "enviar", "aprobar", "rechazar", "anular"]
# S2b.facturacion-v1: La Facturación. super_admin/dueno/contador todo;
# diseñador ninguno.
TODO_FACTURACION = ["ver", "crear", "editar", "emitir", "cobrar", "cancelar"]
# S-Estados-Color-HEX: el chat de El Chalán se gatea por permiso. Default
# activo para los 4 roles (preserva el comportamiento previo); el super_admin
# lo revoca por usuario/rol desde /directorio/<id>/permisos/.
TODO_CHALAN = ["usar"]


DEFAULTS_POR_ROL: dict[str, dict[str, list[str]]] = {
    "super_admin": {
        "cartera": list(TODO_CARTERA),
        "proyectos": list(TODO_PROYECTOS),
        "pizarron": list(TODO_PIZARRON),
        "buzon": list(TODO_BUZON),
        "recados": list(TODO_RECADOS),
        "tesoreria": list(TODO_TESORERIA),
        "dictado": list(TODO_DICTADO),
        "contaduria": list(TODO_CONTADURIA),
        "catalogo": list(TODO_CATALOGO),
        "cotizaciones": list(TODO_COTIZACIONES),
        "facturacion": list(TODO_FACTURACION),
        "chalan": list(TODO_CHALAN),
        # S-LC-Feedback-V5 c5: super_admin entra a La Gerencia por default.
        "gerencia": ["acceder"],
    },
    "dueno": {
        "cartera": list(TODO_CARTERA),
        "proyectos": list(TODO_PROYECTOS),
        "pizarron": list(TODO_PIZARRON),
        "buzon": list(TODO_BUZON),
        "recados": list(TODO_RECADOS),
        "tesoreria": list(TODO_TESORERIA),
        "dictado": list(TODO_DICTADO),
        "contaduria": list(TODO_CONTADURIA),
        # Dueño ve y edita catálogo pero NO gestiona categorías (decisión Pre-S2b.2).
        "catalogo": ["ver_nombres", "ver_precios", "crear", "editar", "editar_precios", "archivar"],
        "cotizaciones": list(TODO_COTIZACIONES),
        "facturacion": list(TODO_FACTURACION),
        "chalan": list(TODO_CHALAN),
        # S-LC-Feedback-V5 c5: dueno entra a La Gerencia por default.
        "gerencia": ["acceder"],
    },
    "contador": {
        # Contador ve cartera read-only; no edita proyectos ni pizarrón.
        "cartera": ["ver"],
        "proyectos": ["ver"],
        "pizarron": ["ver"],
        "buzon": ["ver_propios", "responder"],
        "recados": ["ver", "crear", "editar_propios", "adjuntar_drive"],
        "tesoreria": list(TODO_TESORERIA),
        "dictado": ["registrar_ingreso", "registrar_egreso"],
        "contaduria": list(TODO_CONTADURIA),
        # Contador ve catálogo completo (necesita precios para facturación).
        "catalogo": ["ver_nombres", "ver_precios"],
        # Contador arma y envía cotizaciones pero no aprueba/rechaza/anula.
        "cotizaciones": ["ver", "crear", "editar", "enviar"],
        "facturacion": list(TODO_FACTURACION),
        "chalan": list(TODO_CHALAN),
    },
    "disenador": {
        # Diseñador NO ve cartera (DOC_01 §4.4).
        "proyectos": ["ver", "editar"],  # sólo donde asignado (enforced en views)
        "pizarron": ["ver", "crear", "editar", "completar"],
        "buzon": ["ver_propios", "responder"],
        "recados": ["ver", "crear", "editar_propios", "adjuntar_drive"],
        "dictado": ["actualizar_proyecto", "crear_tarea"],
        # Diseñador ve nombres pero NO precios (default — toggleable individualmente).
        "catalogo": ["ver_nombres"],
        "chalan": list(TODO_CHALAN),
    },
}


def defaults_de(rol: str) -> dict[str, list[str]]:
    """Devuelve dict {modulo: [permisos]} para un rol. Vacío si rol desconocido."""
    return DEFAULTS_POR_ROL.get(rol, {})
