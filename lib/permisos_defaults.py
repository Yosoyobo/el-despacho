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
TODO_CONTADURIA = ["ver", "reconciliar", "exportar"]


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
    },
    "disenador": {
        # Diseñador NO ve cartera (DOC_01 §4.4).
        "proyectos": ["ver", "editar"],  # sólo donde asignado (enforced en views)
        "pizarron": ["ver", "crear", "editar", "completar"],
        "buzon": ["ver_propios", "responder"],
        "recados": ["ver", "crear", "editar_propios", "adjuntar_drive"],
        "dictado": ["actualizar_proyecto", "crear_tarea"],
    },
}


def defaults_de(rol: str) -> dict[str, list[str]]:
    """Devuelve dict {modulo: [permisos]} para un rol. Vacío si rol desconocido."""
    return DEFAULTS_POR_ROL.get(rol, {})
