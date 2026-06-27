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
        "gating": "admin",
    },
    {
        "tipo": "actualizar_proyecto",
        "titulo": "Actualizar proyecto",
        "ejemplo": "Cambia el estado de #lc-0001 a entregado.",
        "payload": "proyecto_slug, campos: {estado?, monto_cotizado?, fecha_compromiso?, descripcion?}",
        "gating": "admin",
    },
    {
        "tipo": "asignar_usuario_proyecto",
        "titulo": "Asignar usuario a proyecto",
        "ejemplo": "Asigna a @ana como líder de #lc-0001.",
        "payload": "proyecto_slug, usuario_slug, rol_en_proyecto? (lider|disenador|produccion|revisor)",
        "gating": "admin",
    },
    {
        "tipo": "agregar_producto_proyecto",
        "titulo": "Agregar producto a un proyecto",
        "ejemplo": 'Agrega 100 playeras a #lc-0001. Los productos se ven SIEMPRE en la página del proyecto, sin importar su estado.',
        "payload": "proyecto_slug (o cliente_slug → su proyecto activo), servicio (nombre del catálogo o @accion_N de un crear_servicio previo), cantidad?, precio_unitario?, costo_unitario?, merma?, proveedor?, nota?",
    },
    {
        "tipo": "crear_cliente",
        "titulo": "Crear cliente",
        "ejemplo": 'Crea un cliente que se llame "NoKo Devs".',
        "payload": "razon_social, rfc?, nombre_contacto?, email_contacto?, telefono?, direccion?, notas?, estado?",
        "gating": "cartera",
    },
    {
        "tipo": "actualizar_cliente",
        "titulo": "Actualizar cliente",
        "ejemplo": "Actualiza el teléfono de $noko-devs a 555-1234.",
        "payload": "cliente_slug, campos: {razon_social?, rfc?, nombre_contacto?, email_contacto?, telefono?, direccion?, notas?, estado?}",
        "gating": "cartera",
    },
    # ── Catálogo: crear productos/variaciones/proveedores (S-Chalan-Barrido).
    # SOLO creación — editar/borrar sigue prohibido (`modificar_catalogo`).
    {
        "tipo": "crear_servicio",
        "titulo": "Crear producto del Catálogo",
        "ejemplo": 'Da de alta el producto "Playera promocional" en la categoría Producción, precio 120, costo 70.',
        "payload": "nombre, precio_base, categoria? (nombre), costo?, unidad?, descripcion?",
        "gating": "catalogo",
    },
    {
        "tipo": "crear_variacion",
        "titulo": "Crear variación de un producto",
        "ejemplo": 'Agrega a "Playera promocional" la variación "Talla M · 1 tinta", costo 80, con impresión $25.',
        "payload": "servicio (@accion_N o nombre), nombre, costo?, impresion_activa?, impresion_costo?, impresion_descripcion?, descripcion?",
        "gating": "catalogo",
    },
    {
        "tipo": "crear_proveedor",
        "titulo": "Crear proveedor",
        "ejemplo": 'Da de alta al proveedor "Telas del Norte", contacto Luis, tel 555-9090.',
        "payload": "razon_social, nombre_contacto?, email_contacto?, telefono?, rfc?, direccion?, notas?",
        "gating": "catalogo",
    },
    {
        "tipo": "crear_tarea",
        "titulo": "Crear tarea (o entrega/recolección)",
        "ejemplo": 'Crea una tarea en #lc-0001: "diseñar logo", asignada a @ana, vence el 30 de mayo. O: "agenda una entrega de #lc-0009 el viernes y que el sistema asigne al runner".',
        "payload": "proyecto_slug (o cliente_slug si solo sabes el cliente: usa su proyecto activo), titulo, asignado_slug?, fecha_compromiso? (SOLO fecha YYYY-MM-DD), hora? (HH:MM aparte — NUNCA metas la hora en fecha_compromiso), prioridad? (baja|media|alta), tipo? (tarea|entrega|junta|recoger), runner_slug?. Si tipo es entrega|recoger el runner se asigna SOLO al crearla (no agregues una acción asignar_runner aparte).",
    },
    {
        "tipo": "actualizar_tarea",
        "titulo": "Actualizar tarea",
        "ejemplo": "Marca como completa la tarea 42.",
        "payload": "tarea_id (acepta @accion_N), campos: {estado?, prioridad?, asignado_slug?, fecha_compromiso? (YYYY-MM-DD), hora? (HH:MM), tipo?}",
    },
    {
        "tipo": "asignar_runner",
        "titulo": "Asignar runner (entrega/recolección)",
        "ejemplo": "Asigna la entrega de la tarea 87 a @beto. O: 'asigna el runner más libre a la tarea 87'.",
        "payload": "tarea_id (acepta @accion_N), runner_slug? (sin él, el sistema asigna el runner menos cargado). NO lo uses tras crear_tarea/crear_mandado de tipo entrega/recoger — esas YA asignan runner solas.",
    },
    {
        "tipo": "crear_mandado",
        "titulo": "Crear mandado (envío/recolección con dirección o lugar)",
        "ejemplo": 'Manda recoger el material de #LC-0001 en "Av. Reforma 222, CDMX". O: "envía la entrega de #LC-0009 a la Sucursal Centro" (lugar conocido).',
        "payload": "proyecto_slug (un mandado cuelga de un proyecto; si solo sabes el cliente pon cliente_slug y el sistema usa su proyecto activo — si tiene varios te pedirá cuál), titulo, tipo? (entrega|recoger), asignado_slug?, fecha_compromiso? (YYYY-MM-DD), hora? (HH:MM), runner_slug?, y el destino: destino_texto (dirección) | poi (nombre de lugar conocido) | destino_lat+destino_lng. Sin runner_slug se asigna al MÁS CERCANO al destino.",
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
        "tipo": "crear_factura",
        "titulo": "Crear factura (borrador)",
        "ejemplo": 'Crea una factura para $karikari por #lc-0009: "Diseño de menú" 1 pieza a $4,500.',
        "payload": "cliente_slug, titulo, items:[{descripcion, precio_unitario, cantidad?, unidad?, descuento_porcentaje?, servicio?}], proyecto_slug?, descuento_global_porcentaje?, notas?, terminos?, impuestos? (default|[nombres])",
        "gating": "facturacion_crear",
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
        "tipo": "crear_cotizacion",
        "titulo": "Crear cotización (borrador)",
        "ejemplo": 'Cotiza a $noko-devs: "Branding completo" — diseño de logo 1 pieza $8,000 y manual de marca 1 pieza $4,000.',
        "payload": "cliente_slug, titulo, items:[{descripcion, precio_unitario, cantidad?, unidad?, descuento_porcentaje?, servicio?}], proyecto_slug?, descuento_global_porcentaje?, notas?, terminos?, impuestos? (default|[nombres])",
        "gating": "cotizaciones_crear",
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
        # S-Chalan-Barrido: gating granular para crear entidades.
        "admin": permisos.es_admin,
        "cartera": permisos.puede_editar_cartera,
        "catalogo": permisos.puede_crear_catalogo,
        "finanzas": permisos.puede_ver_finanzas,
        "facturacion_emitir": permisos.puede_emitir_facturacion,
        "facturacion_cobrar": permisos.puede_cobrar_facturacion,
        "facturacion_crear": permisos.puede_crear_facturacion,
        "cotizaciones_enviar": permisos.puede_enviar_cotizaciones,
        "cotizaciones_aprobar": permisos.puede_aprobar_cotizaciones,
        "cotizaciones_rechazar": permisos.puede_rechazar_cotizaciones,
        "cotizaciones_crear": permisos.puede_crear_cotizaciones,
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
    {"nombre": "resumen_finanzas", "que": "Cómo va el negocio en dinero: ingresos/egresos/utilidad del mes, margen y saldos (requiere permiso de Finanzas). Pregunta informal: «¿cómo vamos de finanzas?»."},
    {"nombre": "resumen_cobranza", "que": "Cómo va la cobranza: CxC total, vencido por antigüedad y top deudores (requiere permiso de Finanzas). Pregunta: «¿cómo va la cobranza?»."},
    {"nombre": "resumen_ventas", "que": "Cómo van las ventas: cotizaciones, conversión y pipeline de proyectos (requiere permiso de Cotizaciones). Pregunta: «¿qué opinas de las ventas este mes?»."},
    {"nombre": "resumen_margenes", "que": "Costos y márgenes del Catálogo: margen promedio y los productos con peor margen (requiere permiso de Finanzas). Pregunta: «¿qué productos dejan poco margen?»."},
    {"nombre": "estado_servidor / specs_servidor", "que": "CPU, memoria, disco, containers, specs (todos los roles)."},
    {"nombre": "📎 imagen", "que": "Adjunta una foto (recibo, ticket) y el Chalán la lee — si el Chalán activo tiene visión."},
]

BANNER_CHAT = (
    "El Chat (El Chalán) consulta estatus en solo-lectura mediante herramientas "
    "vetadas y propone acciones (las de arriba) que tú confirmas. Nunca ejecuta "
    "nada sin confirmación ni responde fuera del contexto del Taller."
)

# S-Chalan-Agente F1: El Chalán es un agente con tool-use nativo + El Relevo
# (ruteo activo al mejor modelo). Texto único para la UI de Gerencia y Taller.
BANNER_RELEVO = (
    "El Chalán es un AGENTE: usa function-calling nativo del proveedor para "
    "consultar datos y encadenar varios pasos por sí mismo antes de responder "
    "(más confiable que el modo anterior). EL RELEVO rutea el pensamiento al "
    "mejor modelo: usa el Chalán rápido (estación «taller_chat») para datos "
    "simples y escala solo al Chalán potente (estación «taller_chat_profundo») "
    "cuando la tarea pide analizar, comparar, planear o redactar. Configura "
    "ambas estaciones en El Cuadro. Las escrituras siguen pasando por "
    "confirmación humana — el agente nunca aplica nada solo."
)


__all__ = [
    "COMANDOS_DICTADO",
    "COMANDOS_PROHIBIDOS",
    "REFERENCIAS_ENTRE_ACCIONES",
    "CONSULTAS_CHAT",
    "BANNER_CHAT",
    "BANNER_RELEVO",
    "comandos_para",
]
