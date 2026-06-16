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
        "titulo": "Crear tarea (o entrega/recolección)",
        "ejemplo": 'Crea una tarea en #lc-0001: "diseñar logo", asignada a @ana, vence el 30 de mayo. O: "agenda una entrega de #lc-0009 el viernes y que el sistema asigne al runner".',
        "payload": "proyecto_slug, titulo, asignado_slug?, fecha_compromiso?, prioridad? (baja|media|alta), tipo? (tarea|entrega|junta|recoger), runner_slug?",
    },
    {
        "tipo": "actualizar_tarea",
        "titulo": "Actualizar tarea",
        "ejemplo": "Marca como completa la tarea 42.",
        "payload": "tarea_id, campos: {estado?, prioridad?, asignado_slug?, fecha_compromiso?}",
    },
    {
        "tipo": "asignar_runner",
        "titulo": "Asignar runner (entrega/recolección)",
        "ejemplo": "Asigna la entrega de la tarea 87 a @beto. O: 'asigna el runner más libre a la tarea 87'.",
        "payload": "tarea_id, runner_slug? (sin él, el sistema asigna el runner menos cargado)",
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
        "gating": "finanzas",
    },
    # ── Fase B (S-Chalán-Scope-OCR): escritura financiera, gateada por permiso.
    {
        "tipo": "registrar_ingreso",
        "titulo": "Registrar ingreso",
        "ejemplo": "Registra un ingreso de $5,000 de $noko-devs por #lc-0001.",
        "payload": "monto, descripcion, cliente_slug?, proyecto_slug?, metodo?, fecha?",
        "gating": "finanzas",
    },
    {
        "tipo": "reembolsar_egreso",
        "titulo": "Reembolsar egreso",
        "ejemplo": "Reembolsa el egreso EGR-2026-0007 por banco.",
        "payload": "codigo, banco_o_caja? (banco|caja), metodo?",
        "gating": "finanzas",
    },
    {
        "tipo": "anular_egreso",
        "titulo": "Anular egreso",
        "ejemplo": "Anula el egreso EGR-2026-0007: se capturó dos veces.",
        "payload": "codigo, motivo",
        "gating": "finanzas",
    },
    {
        "tipo": "anular_ingreso",
        "titulo": "Anular ingreso",
        "ejemplo": "Anula el ingreso ING-2026-0003: fue un error.",
        "payload": "codigo, motivo",
        "gating": "finanzas",
    },
    {
        "tipo": "emitir_factura",
        "titulo": "Emitir factura",
        "ejemplo": "Emite la factura FAC-2026-0012.",
        "payload": "codigo",
        "gating": "facturacion_emitir",
    },
    {
        "tipo": "cobrar_factura",
        "titulo": "Registrar cobro de factura",
        "ejemplo": "Registra un cobro de $3,000 a la factura FAC-2026-0012 por banco.",
        "payload": "codigo, monto, metodo?, banco_o_caja? (banco|caja), fecha?",
        "gating": "facturacion_cobrar",
    },
    {
        "tipo": "enviar_cotizacion",
        "titulo": "Enviar cotización",
        "ejemplo": "Marca como enviada la cotización COT-2026-0005.",
        "payload": "codigo, email?",
        "gating": "cotizaciones_enviar",
    },
    {
        "tipo": "aprobar_cotizacion",
        "titulo": "Aprobar cotización",
        "ejemplo": "Aprueba la cotización COT-2026-0005, la aprobó Juan Pérez.",
        "payload": "codigo, nombre, email?, referencia?",
        "gating": "cotizaciones_aprobar",
    },
    {
        "tipo": "rechazar_cotizacion",
        "titulo": "Rechazar cotización",
        "ejemplo": "Rechaza la cotización COT-2026-0005: el cliente eligió otra opción.",
        "payload": "codigo, motivo",
        "gating": "cotizaciones_rechazar",
    },
    {
        "tipo": "capturar_traspaso",
        "titulo": "Traspaso entre cuentas (contabilidad)",
        "ejemplo": "Traspasa $2,000 de Stripe a banco.",
        "payload": "cuenta_origen, cuenta_destino, monto, descripcion?, fecha?",
        "gating": "contaduria_capturar",
    },
    {
        "tipo": "capturar_ajuste",
        "titulo": "Ajuste de saldo (contabilidad)",
        "ejemplo": "Ajusta el saldo de caja: súbelo $150 por una diferencia de captura.",
        "payload": "cuenta, direccion (sube|baja), monto, motivo, fecha?",
        "gating": "contaduria_capturar",
    },
    {
        "tipo": "enviar_correo",
        "titulo": "Enviar correo a un cliente (El Cartero)",
        "ejemplo": "Mándale un correo a $karikari avisando que su pedido está listo para recolección.",
        "payload": "cliente_slug, tipo_plantilla (generico|bienvenida|cobranza), asunto?, mensaje?",
        "gating": "comunicacion",
    },
    # ── El Checador (S-Chalan-Equipo-UX): el Chalán opera tu asistencia.
    # El actor es siempre quien dicta. Sin GPS (corre en el servidor) → las
    # checadas/visitas quedan sin ubicación; lo más útil es tiempo de proyecto
    # y pedir ajustes de jornada.
    {
        "tipo": "checador_iniciar_jornada",
        "titulo": "Checar entrada (jornada)",
        "ejemplo": "Chécame la entrada.",
        "payload": "(sin payload)",
        "gating": "checador",
    },
    {
        "tipo": "checador_cerrar_jornada",
        "titulo": "Checar salida (jornada)",
        "ejemplo": "Ya me voy, chécame la salida.",
        "payload": "(sin payload)",
        "gating": "checador",
    },
    {
        "tipo": "checador_registrar_tiempo_proyecto",
        "titulo": "Registrar tiempo de proyecto",
        "ejemplo": "Registra 2 horas en #lc-0001 hoy de 10:00 a 12:00.",
        "payload": "proyecto_slug, hora_inicio (HH:MM), hora_fin (HH:MM), fecha?, nota?",
        "gating": "checador",
    },
    {
        "tipo": "checador_iniciar_tiempo_proyecto",
        "titulo": "Iniciar cronómetro de proyecto",
        "ejemplo": "Arranca el cronómetro de #lc-0001.",
        "payload": "proyecto_slug",
        "gating": "checador",
    },
    {
        "tipo": "checador_detener_tiempo_proyecto",
        "titulo": "Detener cronómetro de proyecto",
        "ejemplo": "Detén el cronómetro del proyecto.",
        "payload": "(sin payload)",
        "gating": "checador",
    },
    {
        "tipo": "checador_registrar_visita",
        "titulo": "Registrar visita",
        "ejemplo": "Registra una visita a $karikari.",
        "payload": "cliente_slug? | proveedor_nombre? | tipo? (cliente|proveedor|otro), nota?",
        "gating": "checador",
    },
    {
        "tipo": "checador_solicitar_ajuste_jornada",
        "titulo": "Pedir ajuste de jornada",
        "ejemplo": "Pide ajustar mi jornada de ayer: entré a las 9:00 y salí a las 18:00, olvidé checar.",
        "payload": "fecha (YYYY-MM-DD), hora_entrada? (HH:MM), hora_salida? (HH:MM), motivo",
        "gating": "checador",
    },
]


# Mapa de gating → helper de permisos. "abierto" = todos los roles del Taller.
def _gating_checks():
    from lib import permisos
    return {
        "abierto": lambda u: True,
        "finanzas": permisos.puede_ver_finanzas,
        "facturacion_emitir": permisos.puede_emitir_facturacion,
        "facturacion_cobrar": permisos.puede_cobrar_facturacion,
        "cotizaciones_enviar": permisos.puede_enviar_cotizaciones,
        "cotizaciones_aprobar": permisos.puede_aprobar_cotizaciones,
        "cotizaciones_rechazar": permisos.puede_rechazar_cotizaciones,
        "contaduria_capturar": permisos.puede_capturar_contaduria,
        # V6 Bloque 7B: correo a clientes — permiso granular (comunicacion).
        "comunicacion": permisos.puede_enviar_correo,
        # S-Chalan-Equipo-UX: acciones del Checador (jornada/tiempo/visitas).
        "checador": permisos.puede_checar,
    }


def comandos_para(usuario) -> list[dict]:
    """Comandos del Dictado que el usuario puede ejecutar según su rol.

    El prompt enumera solo lo permitido (regla de seguridad #2); el ejecutor
    re-chequea el permiso al aplicar (defensa en profundidad)."""
    checks = _gating_checks()
    out = []
    for c in COMANDOS_DICTADO:
        fn = checks.get(c.get("gating", "abierto"))
        if fn is None or fn(usuario):
            out.append(c)
    return out

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
        "tipo": "timbrar_cfdi",
        "razon": "El Despacho no timbra; el contador externo emite el CFDI aparte.",
    },
    {
        "tipo": "cancelar_factura_cobrada",
        "razon": "Una factura con cobros no se cancela; primero se anula el ingreso.",
    },
]


# S-Chalan-Chat-V1: el Chat del Taller (El Chalán, ruta /chalan/) además de
# proponer las acciones de arriba, puede CONSULTAR datos en solo-lectura vía
# herramientas vetadas. Aquí se documentan para la UI de Los Chalanes.
CONSULTAS_CHAT: list[dict] = [
    {"nombre": "listar_kpis / consultar_kpi", "que": "Indicadores del tablero (según el rol)."},
    {"nombre": "consultar_metrica", "que": "Conteos/sumas acotadas (proyectos, tareas, clientes, ingresos/egresos)."},
    {"nombre": "buscar", "que": "Búsqueda libre por texto en proyectos, clientes, facturas y cotizaciones."},
    {"nombre": "detalle_proyecto", "que": "Estatus de un proyecto por código LC-NNNN o nombre."},
    {"nombre": "tareas_de_proyecto / mis_tareas / detalle_tarea", "que": "Tareas de un proyecto, tus tareas abiertas, o el detalle de una."},
    {"nombre": "detalle_cliente", "que": "Datos de un cliente (requiere permiso de Clientes)."},
    {"nombre": "detalle_factura / detalle_cotizacion / detalle_ingreso", "que": "Estatus por código (requiere permiso)."},
    {"nombre": "contaduria_saldo_cuenta / contaduria_balance", "que": "Saldos contables y balance (requiere permiso de Contaduría)."},
    {"nombre": "proximos_eventos", "que": "Entregas y tareas con fecha en los próximos días."},
    {"nombre": "mi_jornada_hoy / mis_horas_semana", "que": "Tu jornada de hoy (entrada/salida/retardo) y tus horas de los últimos 7 días (El Checador)."},
    {"nombre": "resumen del calendario", "que": "En la página de Calendario, el botón '🤖 Resumir con El Chalán' arma un resumen ejecutivo de tus próximas entregas y tareas (qué viene, qué urge)."},
    {"nombre": "gasto_ia", "que": "Costo, llamadas y tokens de IA por proveedor."},
    {"nombre": "estado_servidor / specs_servidor", "que": "CPU, memoria, disco, containers, specs (todos los roles)."},
    {"nombre": "📎 imagen", "que": "Adjunta una foto (recibo, ticket) y el Chalán la lee — si el Chalán activo tiene visión."},
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
    "comandos_para",
]
