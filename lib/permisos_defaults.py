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
# S-Checador: asistencia. `checar` es para todo el staff; las funciones de
# supervisión (ver equipo, aprobar correcciones, configurar horarios,
# exportar) son de admin.
TODO_CHECADOR = ["checar", "ver_equipo", "aprobar_correcciones", "configurar_horarios", "exportar"]
# V6 Bloque 7: Comunicaciones — correos a clientes vía El Chalán y campañas
# masivas. Default SOLO super_admin (decisión Oscar: gating 100% granular,
# el resto lo recibe vía la grilla de permisos o roles personalizados).
TODO_COMUNICACION = ["enviar_correo", "campanas"]


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
        "checador": list(TODO_CHECADOR),
        "comunicacion": list(TODO_COMUNICACION),
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
        "checador": list(TODO_CHECADOR),
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
        # Contador checa, ve al equipo y exporta (insumo para nómina/costos);
        # no aprueba correcciones ni configura horarios.
        "checador": ["checar", "ver_equipo", "exportar"],
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
        # Diseñador solo checa su propia jornada/visitas/tiempo.
        "checador": ["checar"],
    },
}


# Catálogo canónico módulo→acciones. FUENTE ÚNICA para los editores de permisos
# (grilla del form de Rol y grilla por-usuario). Incluye TODAS las acciones de
# cada módulo — independiente del rol primario, para poder conceder cualquier
# permiso a cualquier usuario (incluido `miembro`, que no tiene defaults).
CATALOGO_PERMISOS: dict[str, list[str]] = {
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
    "checador": list(TODO_CHECADOR),
    "comunicacion": list(TODO_COMUNICACION),
    "gerencia": ["acceder"],
}


def defaults_de(rol: str) -> dict[str, list[str]]:
    """Devuelve dict {modulo: [permisos]} para un rol. Vacío si rol desconocido."""
    return DEFAULTS_POR_ROL.get(rol, {})


def catalogo_permisos() -> dict[str, list[str]]:
    """Catálogo canónico módulo→[acciones] — todas las acciones de cada módulo."""
    return {m: list(a) for m, a in CATALOGO_PERMISOS.items()}
