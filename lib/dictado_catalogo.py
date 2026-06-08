"""Catálogo de comandos que El Dictado puede ejecutar.

Fuente única de verdad para la UI de Los Chalanes (qué SÍ y qué NO puede
hacer un dictado). El prompt del Dictado y los ejecutores reales viven en
`apps.el_dictado.*` (Taller); este módulo está en `lib/` para que La
Gerencia lo pueda importar sin acoplarse al proyecto Taller.

Si agregas un ejecutor nuevo en `apps/el_dictado/ejecutores/`, agrégalo
también aquí y al prompt en `apps/el_dictado/prompt.py`.
"""

from __future__ import annotations

REFERENCIAS_ENTRE_ACCIONES = (
    "Si una acción depende de una entidad creada por otra acción del MISMO "
    "dictado, el Chalán puede usar `@accion_N` (donde N es el índice de la "
    "acción que la creó) en lugar de un slug. Ej: crear proyecto + asignar "
    "líder en un solo dictado — el segundo usa `proyecto_slug: \"@accion_0\"`. "
    "Si el Chalán adivina un slug parecido al nombre, el sistema también "
    "hace fuzzy match contra las entidades recién creadas."
)


COMANDOS_DICTADO: list[dict] = [
    {
        "tipo": "crear_proyecto",
        "titulo": "Crear proyecto",
        "ejemplo": 'Crea un proyecto "branding" para $noko-devs.',
        "payload": "nombre, cliente_slug, descripcion?, estado?, fecha_compromiso?, monto_estimado?, monto_cotizado?",
    },
    {
        "tipo": "actualizar_proyecto",
        "titulo": "Actualizar proyecto",
        "ejemplo": "Cambia el estado de #lc-0001 a entregado.",
        "payload": "proyecto_slug, campos: {estado?, monto_cotizado?, fecha_compromiso?, descripcion?}",
    },
    {
        "tipo": "asignar_usuario_proyecto",
        "titulo": "Asignar usuario a proyecto",
        "ejemplo": "Asigna a @ana como líder de #lc-0001.",
        "payload": "proyecto_slug, usuario_slug, rol_en_proyecto? (lider|disenador|produccion|revisor)",
    },
    {
        "tipo": "crear_cliente",
        "titulo": "Crear cliente",
        "ejemplo": 'Crea un cliente que se llame "NoKo Devs".',
        "payload": "razon_social, rfc?, nombre_contacto?, email_contacto?, telefono?, direccion?, notas?, estado?",
    },
    {
        "tipo": "actualizar_cliente",
        "titulo": "Actualizar cliente",
        "ejemplo": "Actualiza el teléfono de $noko-devs a 555-1234.",
        "payload": "cliente_slug, campos: {razon_social?, rfc?, nombre_contacto?, email_contacto?, telefono?, direccion?, notas?, estado?}",
    },
    {
        "tipo": "crear_tarea",
        "titulo": "Crear tarea",
        "ejemplo": 'Crea una tarea en #lc-0001: "diseñar logo", asignada a @ana, vence el 30 de mayo.',
        "payload": "proyecto_slug, titulo, asignado_slug?, fecha_compromiso?, prioridad? (baja|media|alta)",
    },
    {
        "tipo": "actualizar_tarea",
        "titulo": "Actualizar tarea",
        "ejemplo": "Marca como completa la tarea 42.",
        "payload": "tarea_id, campos: {estado?, prioridad?, asignado_slug?, fecha_compromiso?}",
    },
    {
        "tipo": "crear_recado",
        "titulo": "Crear recado",
        "ejemplo": "Mándale a @ana un recado: que revise #lc-0001 mañana.",
        "payload": "destinatarios_slugs: [...], cuerpo",
    },
    {
        "tipo": "crear_mensaje_buzon",
        "titulo": "Crear mensaje en El Buzón",
        "ejemplo": "Sugerencia para el Buzón: agregar export de tareas a CSV.",
        "payload": "tipo (sugerencia|problema|otro), asunto, cuerpo",
    },
    {
        "tipo": "registrar_egreso",
        "titulo": "Registrar egreso",
        "ejemplo": "Registra un gasto de $450 en papelería, pagado con tarjeta personal.",
        "payload": "monto, descripcion, centro_de_costo_slug, proyecto_slug?, proveedor_nombre?, pagado_por_slug?, estado_pago?, metodo?, fecha?",
    },
]

# Acciones que el Chalán nunca puede ejecutar, aunque el LLM las proponga.
# El service `interpretar()` las filtra en `TIPOS_PROHIBIDOS` antes de
# persistir; aquí se documentan para la UI.
COMANDOS_PROHIBIDOS: list[dict] = [
    {
        "tipo": "modificar_ajustes",
        "razon": "Las credenciales (La Bóveda) solo se editan desde Los Ajustes.",
    },
    {
        "tipo": "modificar_catalogo",
        "razon": "Servicios y variaciones se administran manualmente en El Catálogo.",
    },
    {
        "tipo": "modificar_tasas",
        "razon": "Las tasas impositivas requieren validación contable manual.",
    },
    {
        "tipo": "modificar_centro_costo",
        "razon": "Los centros de costo los administra La Gerencia.",
    },
    {
        "tipo": "modificar_permisos",
        "razon": "Solo super_admin asigna permisos desde El Directorio.",
    },
    {
        "tipo": "eliminar_entidad",
        "razon": "El dictado nunca borra — soft-delete o anulación se hacen desde su módulo.",
    },
    {
        "tipo": "registrar_ingreso",
        "razon": "Pendiente: los cobros casi siempre tienen factura referenciada. Se captura desde La Caja o La Tesorería.",
    },
]


# S-Chalan-Chat-V1: el Chat del Taller (El Chalán, ruta /chalan/) además de
# proponer las acciones de arriba, puede CONSULTAR datos en solo-lectura vía
# herramientas vetadas. Aquí se documentan para la UI de Los Chalanes.
CONSULTAS_CHAT: list[dict] = [
    {"nombre": "listar_kpis / consultar_kpi", "que": "Indicadores del tablero (según el rol)."},
    {"nombre": "consultar_metrica", "que": "Conteos/sumas acotadas (proyectos, tareas, clientes, ingresos/egresos)."},
    {"nombre": "detalle_proyecto", "que": "Estatus de un proyecto por código LC-NNNN o nombre."},
    {"nombre": "detalle_cliente", "que": "Datos de un cliente (requiere permiso de Clientes)."},
    {"nombre": "detalle_factura / detalle_cotizacion", "que": "Estatus por código (requiere permiso)."},
    {"nombre": "gasto_ia", "que": "Costo, llamadas y tokens de IA por proveedor."},
    {"nombre": "estado_servidor / specs_servidor", "que": "CPU, memoria, disco, containers, specs (todos los roles)."},
]

BANNER_CHAT = (
    "El Chat (El Chalán) consulta estatus en solo-lectura mediante herramientas "
    "vetadas y propone acciones (las de arriba) que tú confirmas. Nunca ejecuta "
    "nada sin confirmación ni responde fuera del contexto del Taller."
)


__all__ = [
    "COMANDOS_DICTADO",
    "COMANDOS_PROHIBIDOS",
    "REFERENCIAS_ENTRE_ACCIONES",
    "CONSULTAS_CHAT",
    "BANNER_CHAT",
]
