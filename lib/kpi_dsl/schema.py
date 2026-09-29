"""Whitelists del DSL — todo lo NO listado aquí queda prohibido.

v2 (constructor de KPIs de La Gerencia): cada entidad declara, además de su
modelo, los CAMPOS con su tipo y etiqueta en español, las AGRUPACIONES
permitidas, las DURACIONES nombradas entre dos fechas y el PERMISO granular
que hace falta para ver su dato (§4 #20: nunca un rol). La UI arma el
formulario sola con `esquema_para_ui()`; El Chalán arma su prompt con lo mismo.

Una llave de campo es el nombre que usa la definición; su `ruta` (si la
trae) es el camino del ORM. Sin `ruta`, la llave ES el campo del modelo. Nada
que no esté aquí llega al ORM: el validador sólo deja pasar llaves de este
archivo y el ejecutor sólo usa las `ruta` de este archivo.

Retrocompatibilidad v1: `campos_numericos` y `campos_filtrables` se DERIVAN de
`campos` al importar (los leen el prompt viejo y el candado de campos). Todo
campo y operador que v1 aceptaba sigue aceptado.
"""

from __future__ import annotations

# ── Tipos de campo y lo que cada uno admite ──────────────────────────────────

TIPOS_CAMPO = ("texto", "numero", "dinero", "fecha", "booleano", "opcion", "relacion")

OPS_POR_TIPO: dict[str, tuple[str, ...]] = {
    "texto": ("eq", "in", "contiene", "vacio"),
    "numero": ("eq", "gt", "gte", "lt", "lte", "vacio"),
    "dinero": ("eq", "gt", "gte", "lt", "lte", "vacio"),
    "fecha": ("eq", "gt", "gte", "lt", "lte", "vacio"),
    "booleano": ("eq",),
    "opcion": ("eq", "in"),
    "relacion": ("eq", "in", "vacio"),
}

# Tipos que se pueden sumar/promediar. count no lleva campo.
TIPOS_AGREGABLES = ("numero", "dinero")

ETIQUETAS_OPS = {
    "eq": "es igual a",
    "in": "es alguno de",
    "gt": "es mayor que",
    "gte": "es mayor o igual que",
    "lt": "es menor que",
    "lte": "es menor o igual que",
    "contiene": "contiene",
    "vacio": "está vacío",
}
# Cómo se lee cada operador cuando el campo es una fecha.
ETIQUETAS_OPS_FECHA = {
    "eq": "es el",
    "gt": "es después de",
    "gte": "es desde",
    "lt": "es antes de",
    "lte": "es hasta",
    "vacio": "está vacía",
}


def _c(etiqueta: str, tipo: str, **extra) -> dict:
    """Un campo: etiqueta en minúsculas (se usa a media frase), tipo y extras
    (`ruta`, `permiso`, `formato`, `catalogo`, `genero`, `ops`)."""
    return {"etiqueta": etiqueta, "tipo": tipo, **extra}


def _g(etiqueta: str, ruta: str) -> dict:
    """Una agrupación: por qué se reparte el número."""
    return {"etiqueta": etiqueta, "ruta": ruta}


def _d(etiqueta: str, desde: str, hasta: str, unidad: str = "dias") -> dict:
    """Una duración nombrada: de la llave-campo `desde` a la llave-campo
    `hasta` (ambos del tipo fecha de la misma entidad), medida en `unidad`."""
    return {"etiqueta": etiqueta, "desde": desde, "hasta": hasta, "unidad": unidad}


# El dinero del proyecto lo ve quien ve la Tesorería (`puede_ver_finanzas`).
_DINERO = ("tesoreria.ver",)

# Cada entrada describe:
# - modelo: path lazy «app_label.Modelo».
# - etiqueta / etiqueta_singular / genero («m»|«f»): para la UI y `describir`.
# - campo_fecha: la llave-campo de fecha a la que se aplica la ventana por
#   default (la definición puede escoger otro campo de tipo fecha).
# - link_default: a dónde manda el «Ver más».
# - campo_autor / campo_asignado: rutas para `alcance_usuario="mio"`.
# - permiso: lo que hay que tener para ver el dato de TODO el despacho.
#   permiso_mio: lo que basta con `alcance_usuario="mio"` (default: `permiso`).
#   Tuplas «modulo.accion»; hacen falta TODAS; super_admin siempre (failsafe).
# - campos, agrupaciones, duraciones: la whitelist.
ENTIDADES: dict[str, dict] = {
    "proyecto": {
        "modelo": "proyectos.Proyecto",
        "etiqueta": "proyectos", "etiqueta_singular": "proyecto", "genero": "m",
        "campo_fecha": "creado_en",
        "link_default": "/proyectos/",
        "campo_autor": None,
        "campo_asignado": "asignaciones__usuario",
        "permiso": ("proyectos.ver_todos",),
        "permiso_mio": ("proyectos.ver",),
        "campos": {
            "estado": _c("estado", "opcion", catalogo="proyectos.EstadoProyecto"),
            "archivado": _c("archivado", "booleano"),
            "cliente": _c("cliente", "relacion"),
            "nombre": _c("nombre", "texto"),
            "regimen_fiscal": _c("régimen fiscal", "opcion"),
            "motivo_cancelacion": _c("motivo de cancelación", "relacion"),
            "monto_estimado": _c("monto estimado", "dinero", permiso=_DINERO),
            "monto_cotizado": _c("monto cotizado", "dinero", permiso=_DINERO),
            "monto_facturado": _c("monto facturado", "dinero", permiso=_DINERO),
            "monto_cobrado": _c("monto cobrado", "dinero", permiso=_DINERO),
            "creado_en": _c("fecha de alta", "fecha", genero="f"),
            "fecha_inicio": _c("fecha de inicio", "fecha", genero="f"),
            "fecha_compromiso": _c("fecha de compromiso", "fecha", genero="f"),
            "fecha_real_entrega": _c("fecha real de entrega", "fecha", genero="f"),
            "cancelado_en": _c("fecha de cancelación", "fecha", genero="f"),
        },
        "agrupaciones": {
            "cliente": _g("cliente", "cliente"),
            "estado": _g("estado", "estado"),
            "persona": _g("persona asignada", "asignaciones__usuario"),
            "motivo_cancelacion": _g("motivo de cancelación", "motivo_cancelacion"),
        },
        "duraciones": {
            "dias_para_entregar": _d("días para entregar", "creado_en", "fecha_real_entrega"),
            "dias_de_retraso": _d("días de retraso en la entrega (negativo = antes)",
                                  "fecha_compromiso", "fecha_real_entrega"),
        },
    },
    "tarea": {
        "modelo": "pizarron.Tarea",
        "etiqueta": "tareas", "etiqueta_singular": "tarea", "genero": "f",
        "campo_fecha": "creado_en",
        "link_default": "/tareas/",
        "campo_autor": "creado_por",
        "campo_asignado": "asignada_a",
        # Las tareas heredan la visibilidad del proyecto (`puede_ver_tarea`).
        "permiso": ("pizarron.ver", "proyectos.ver_todos"),
        "permiso_mio": ("pizarron.ver",),
        "campos": {
            "estado": _c("estado", "opcion", catalogo="pizarron.EstadoTarea"),
            "prioridad": _c("prioridad", "opcion", genero="f"),
            "tipo": _c("tipo", "opcion"),
            "titulo": _c("título", "texto"),
            "archivada": _c("archivada", "booleano"),
            "requiere_runner": _c("requiere runner", "booleano"),
            "asignada_a": _c("persona asignada", "relacion", genero="f"),
            "proyecto": _c("proyecto", "relacion"),
            "creado_en": _c("fecha de alta", "fecha", genero="f"),
            "fecha_compromiso": _c("fecha de compromiso", "fecha", genero="f"),
            "completada_en": _c("fecha en que se completó", "fecha", genero="f"),
        },
        "agrupaciones": {
            "persona": _g("persona asignada", "asignada_a"),
            "proyecto": _g("proyecto", "proyecto"),
            "cliente": _g("cliente", "proyecto__cliente"),
            "estado": _g("estado", "estado"),
            "prioridad": _g("prioridad", "prioridad"),
            "tipo": _g("tipo", "tipo"),
        },
        "duraciones": {
            "dias_para_cerrar": _d("días para completarla", "creado_en", "completada_en"),
            "dias_de_retraso": _d("días de retraso (negativo = antes)",
                                  "fecha_compromiso", "completada_en"),
        },
    },
    "cliente": {
        "modelo": "cartera.Cliente",
        "etiqueta": "clientes", "etiqueta_singular": "cliente", "genero": "m",
        "campo_fecha": "creado_en",
        "link_default": "/cartera/",
        "campo_autor": None,
        "campo_asignado": None,
        "permiso": ("cartera.ver",),
        "campos": {
            "activo": _c("activo", "booleano"),
            "estado": _c("estado", "opcion"),
            "razon_social": _c("razón social", "texto", genero="f"),
            "creado_en": _c("fecha de alta", "fecha", genero="f"),
        },
        "agrupaciones": {
            "estado": _g("estado", "estado"),
        },
        "duraciones": {},
    },
    "egreso": {
        "modelo": "tesoreria.Egreso",
        "etiqueta": "egresos", "etiqueta_singular": "egreso", "genero": "m",
        "campo_fecha": "fecha",
        "link_default": "/tesoreria/egresos/",
        "campo_autor": "creado_por",
        "campo_asignado": None,
        "permiso": ("tesoreria.ver",),
        "campos": {
            "monto": _c("monto", "dinero"),
            "subtotal": _c("subtotal", "dinero"),
            "estado_pago": _c("estado de pago", "opcion"),
            "metodo": _c("método de pago", "opcion"),
            "origen": _c("origen", "opcion"),
            "anulado": _c("anulado", "booleano"),
            "incluye_iva": _c("incluye IVA", "booleano"),
            "tiene_comprobante": _c("tiene comprobante", "booleano"),
            # Búsqueda por texto: "gasto en ubers" → descripcion/proveedor contiene 'uber'.
            "descripcion": _c("descripción", "texto", genero="f"),
            "proveedor_nombre": _c("nombre del proveedor", "texto"),
            "proveedor": _c("proveedor", "relacion"),
            "centro_de_costo": _c("centro de costo", "relacion"),
            "proyecto": _c("proyecto", "relacion"),
            "solicitado_por": _c("quién lo solicitó", "relacion"),
            "pagado_por": _c("quién lo pagó", "relacion"),
            "fecha": _c("fecha", "fecha", genero="f"),
            "pagado_en": _c("fecha de pago", "fecha", genero="f"),
        },
        "agrupaciones": {
            "proveedor": _g("proveedor", "proveedor"),
            "centro_de_costo": _g("centro de costo", "centro_de_costo"),
            "proyecto": _g("proyecto", "proyecto"),
            "cliente": _g("cliente", "proyecto__cliente"),
            "estado_pago": _g("estado de pago", "estado_pago"),
            "metodo": _g("método de pago", "metodo"),
            "persona": _g("quién lo capturó", "creado_por"),
            "solicitado_por": _g("quién lo solicitó", "solicitado_por"),
        },
        "duraciones": {
            "dias_para_pagar": _d("días para pagarlo", "fecha", "pagado_en"),
        },
    },
    "ingreso": {
        "modelo": "tesoreria.Ingreso",
        "etiqueta": "ingresos", "etiqueta_singular": "ingreso", "genero": "m",
        "campo_fecha": "fecha",
        "link_default": "/tesoreria/ingresos/",
        "campo_autor": "creado_por",
        "campo_asignado": None,
        "permiso": ("tesoreria.ver",),
        "campos": {
            "monto": _c("monto", "dinero"),
            "subtotal": _c("subtotal", "dinero"),
            "metodo": _c("método de pago", "opcion"),
            "anulado": _c("anulado", "booleano"),
            "incluye_iva": _c("incluye IVA", "booleano"),
            "tiene_comprobante": _c("tiene comprobante", "booleano"),
            "descripcion": _c("descripción", "texto", genero="f"),
            "cliente": _c("cliente", "relacion"),
            "proyecto": _c("proyecto", "relacion"),
            "factura": _c("factura", "relacion", genero="f"),
            "fecha": _c("fecha", "fecha", genero="f"),
        },
        "agrupaciones": {
            "cliente": _g("cliente", "cliente"),
            "proyecto": _g("proyecto", "proyecto"),
            "metodo": _g("método de pago", "metodo"),
            "persona": _g("quién lo capturó", "creado_por"),
        },
        "duraciones": {},
    },
    "recado": {
        "modelo": "recados.Recado",
        "etiqueta": "recados", "etiqueta_singular": "recado", "genero": "m",
        "campo_fecha": "creado_en",
        "link_default": "/recados/legacy/",
        "campo_autor": "autor",
        "campo_asignado": None,
        "permiso": ("recados.ver_historial_todos",),
        "permiso_mio": ("recados.ver",),
        "campos": {
            "editado": _c("editado", "booleano"),
            "creado_en": _c("fecha", "fecha", genero="f"),
        },
        "agrupaciones": {
            "persona": _g("autor", "autor"),
        },
        "duraciones": {},
    },
    "buzon_mensaje": {
        "modelo": "buzon.MensajeBuzon",
        "etiqueta": "mensajes del buzón", "etiqueta_singular": "mensaje del buzón", "genero": "m",
        "campo_fecha": "creado_en",
        "link_default": "/buzon/",
        "campo_autor": "autor",
        "campo_asignado": None,
        # El dato es `buzon.ver_todos`, pero ése sólo lo trae el super_admin y
        # el dueño ve estos números en La Sala de Juntas: se usa la misma
        # acción que el catálogo (`permisos_kpi.ATIENDE_SOPORTE`).
        "permiso": ("buzon.eliminar",),
        "permiso_mio": ("buzon.ver_propios",),
        "campos": {
            "tipo": _c("tipo", "opcion", catalogo="buzon.TipoBuzon"),
            "estado": _c("estado", "opcion", catalogo="buzon.EstadoBuzon"),
            "asunto": _c("asunto", "texto"),
            "prioridad": _c("prioridad", "numero", genero="f"),
            "respondido_por": _c("quién respondió", "relacion"),
            "creado_en": _c("fecha", "fecha", genero="f"),
            "respondido_en": _c("fecha de respuesta", "fecha", genero="f"),
        },
        "agrupaciones": {
            "tipo": _g("tipo", "tipo"),
            "estado": _g("estado", "estado"),
            "persona": _g("autor", "autor"),
            "respondido_por": _g("quién respondió", "respondido_por"),
        },
        "duraciones": {
            "horas_para_responder": _d("horas para responder", "creado_en", "respondido_en", "horas"),
        },
    },
    "cotizacion": {
        "modelo": "cotizaciones.Cotizacion",
        "etiqueta": "cotizaciones", "etiqueta_singular": "cotización", "genero": "f",
        "campo_fecha": "fecha_emision",
        "link_default": "/cotizaciones/",
        "campo_autor": "creado_por",
        "campo_asignado": None,
        "permiso": ("cotizaciones.ver",),
        "campos": {
            "estado": _c("estado", "opcion"),
            "cliente": _c("cliente", "relacion"),
            "proyecto": _c("proyecto", "relacion"),
            "titulo": _c("título", "texto"),
            "regimen_fiscal": _c("régimen fiscal", "opcion"),
            "forma_pago": _c("forma de pago", "opcion", genero="f"),
            "version": _c("versión", "numero", genero="f"),
            "anticipo_porcentaje": _c("porcentaje de anticipo", "numero", formato="pct"),
            "descuento_global_porcentaje": _c("porcentaje de descuento", "numero", formato="pct"),
            "fecha_emision": _c("fecha de emisión", "fecha", genero="f"),
            "fecha_validez": _c("fecha de validez", "fecha", genero="f"),
            "creado_en": _c("fecha de alta", "fecha", genero="f"),
            "enviada_en": _c("fecha de envío", "fecha", genero="f"),
            "aprobada_en": _c("fecha de aprobación", "fecha", genero="f"),
            "rechazada_en": _c("fecha de rechazo", "fecha", genero="f"),
            "pagada_en": _c("fecha de pago", "fecha", genero="f"),
            "anulada_en": _c("fecha de anulación", "fecha", genero="f"),
        },
        "agrupaciones": {
            "cliente": _g("cliente", "cliente"),
            "proyecto": _g("proyecto", "proyecto"),
            "estado": _g("estado", "estado"),
            "persona": _g("quién la hizo", "creado_por"),
        },
        "duraciones": {
            "dias_para_enviar": _d("días para enviarla", "creado_en", "enviada_en"),
            "dias_para_aprobar": _d("días para que la aprueben", "enviada_en", "aprobada_en"),
            "dias_para_rechazar": _d("días para que la rechacen", "enviada_en", "rechazada_en"),
            "dias_para_pagar": _d("días para que la paguen", "aprobada_en", "pagada_en"),
        },
    },
    "factura": {
        "modelo": "facturacion.Factura",
        "etiqueta": "facturas", "etiqueta_singular": "factura", "genero": "f",
        "campo_fecha": "fecha_emision",
        "link_default": "/facturacion/",
        "campo_autor": "creado_por",
        "campo_asignado": None,
        "permiso": ("facturacion.ver",),
        "campos": {
            "estado": _c("estado", "opcion"),
            "cliente": _c("cliente", "relacion"),
            "proyecto": _c("proyecto", "relacion"),
            "cotizacion_origen": _c("cotización de origen", "relacion", genero="f"),
            "titulo": _c("título", "texto"),
            "cfdi_uuid": _c("UUID del CFDI", "texto"),
            "regimen_fiscal": _c("régimen fiscal", "opcion"),
            "monto_cobrado": _c("monto cobrado", "dinero"),
            "porcentaje_a_facturar": _c("porcentaje a facturar", "numero", formato="pct"),
            "fecha_emision": _c("fecha de emisión", "fecha", genero="f"),
            "fecha_vencimiento": _c("fecha de vencimiento", "fecha", genero="f"),
            "creado_en": _c("fecha de alta", "fecha", genero="f"),
            "emitida_en": _c("fecha en que se emitió", "fecha", genero="f"),
            "cancelada_en": _c("fecha de cancelación", "fecha", genero="f"),
        },
        "agrupaciones": {
            "cliente": _g("cliente", "cliente"),
            "proyecto": _g("proyecto", "proyecto"),
            "estado": _g("estado", "estado"),
            "persona": _g("quién la hizo", "creado_por"),
        },
        "duraciones": {
            "dias_de_credito": _d("días de crédito", "fecha_emision", "fecha_vencimiento"),
            "dias_para_emitir": _d("días para emitirla", "creado_en", "emitida_en"),
        },
    },
    "jornada": {
        "modelo": "checador.Jornada",
        "etiqueta": "jornadas", "etiqueta_singular": "jornada", "genero": "f",
        "campo_fecha": "fecha",
        "link_default": "/checador/",
        "campo_autor": "usuario",
        "campo_asignado": None,
        "permiso": ("checador.ver_equipo",),
        "permiso_mio": ("checador.checar",),
        "campos": {
            "usuario": _c("persona", "relacion", genero="f"),
            "estado": _c("estado", "opcion"),
            "sede": _c("sede", "relacion", genero="f"),
            "retardo_min": _c("minutos de retardo", "numero", formato="minutos"),
            "minutos_extra": _c("minutos extra", "numero", formato="minutos"),
            "salida_automatica": _c("salida automática", "booleano"),
            "entrada_sin_geo": _c("entrada sin ubicación", "booleano"),
            "entrada_offline": _c("entrada sin conexión", "booleano"),
            "fecha": _c("fecha", "fecha", genero="f"),
            "entrada_en": _c("hora de entrada", "fecha", genero="f"),
            "salida_en": _c("hora de salida", "fecha", genero="f"),
        },
        "agrupaciones": {
            "persona": _g("persona", "usuario"),
            "sede": _g("sede", "sede"),
            "estado": _g("estado", "estado"),
        },
        "duraciones": {
            "horas_trabajadas": _d("horas trabajadas", "entrada_en", "salida_en", "horas"),
        },
    },
    "sesion_proyecto": {
        "modelo": "checador.SesionProyecto",
        "etiqueta": "sesiones de trabajo en proyectos", "etiqueta_singular": "sesión de trabajo",
        "genero": "f",
        "campo_fecha": "inicio",
        "link_default": "/checador/",
        "campo_autor": "usuario",
        "campo_asignado": None,
        "permiso": ("checador.ver_equipo",),
        "permiso_mio": ("checador.checar",),
        "campos": {
            "usuario": _c("persona", "relacion", genero="f"),
            "proyecto": _c("proyecto", "relacion"),
            "origen": _c("origen", "opcion"),
            "estado": _c("estado", "opcion"),
            "sin_geo": _c("sin ubicación", "booleano"),
            "duracion_min": _c("duración en minutos", "numero", formato="minutos", genero="f"),
            "inicio": _c("inicio", "fecha"),
            "fin": _c("fin", "fecha"),
        },
        "agrupaciones": {
            "persona": _g("persona", "usuario"),
            "proyecto": _g("proyecto", "proyecto"),
            "cliente": _g("cliente", "proyecto__cliente"),
            "origen": _g("origen", "origen"),
        },
        "duraciones": {
            "horas": _d("horas de trabajo", "inicio", "fin", "horas"),
        },
    },
    "visita": {
        "modelo": "checador.Visita",
        "etiqueta": "visitas", "etiqueta_singular": "visita", "genero": "f",
        "campo_fecha": "registrado_en",
        "link_default": "/checador/",
        "campo_autor": "usuario",
        "campo_asignado": None,
        "permiso": ("checador.ver_equipo",),
        "permiso_mio": ("checador.checar",),
        "campos": {
            "usuario": _c("persona", "relacion", genero="f"),
            "tipo": _c("tipo", "opcion"),
            "proposito": _c("propósito", "opcion"),
            "cliente": _c("cliente", "relacion"),
            "proveedor": _c("proveedor", "relacion"),
            "tarea": _c("tarea", "relacion", genero="f"),
            "sin_geo": _c("sin ubicación", "booleano"),
            "capturada_offline": _c("capturada sin conexión", "booleano"),
            "registrado_en": _c("fecha", "fecha", genero="f"),
        },
        "agrupaciones": {
            "persona": _g("persona", "usuario"),
            "tipo": _g("tipo", "tipo"),
            "cliente": _g("cliente", "cliente"),
            "proveedor": _g("proveedor", "proveedor"),
            "proposito": _g("propósito", "proposito"),
        },
        "duraciones": {},
    },
    "cfdi_entrante": {
        "modelo": "facturacion.CfdiEntrante",
        "etiqueta": "CFDI recibidos", "etiqueta_singular": "CFDI recibido", "genero": "m",
        "campo_fecha": "recibido_en",
        "link_default": "/tesoreria/cfdi-recibidos/",
        "campo_autor": None,
        "campo_asignado": None,
        # La bandeja de CFDI recibidos pide `tesoreria.ver` (views_cfdi).
        "permiso": ("tesoreria.ver",),
        "campos": {
            "estado": _c("estado", "opcion"),
            "emisor_rfc": _c("RFC del emisor", "texto"),
            "emisor_nombre": _c("nombre del emisor", "texto"),
            "concepto": _c("concepto", "texto"),
            "total": _c("total", "dinero"),
            "subtotal": _c("subtotal", "dinero"),
            "iva": _c("IVA", "dinero"),
            "proveedor": _c("proveedor", "relacion"),
            "factura": _c("factura", "relacion", genero="f"),
            "egreso": _c("egreso", "relacion"),
            "recibido_en": _c("fecha en que llegó", "fecha", genero="f"),
            "resuelto_en": _c("fecha en que se resolvió", "fecha", genero="f"),
        },
        "agrupaciones": {
            "proveedor": _g("proveedor", "proveedor"),
            "estado": _g("estado", "estado"),
            "emisor": _g("emisor", "emisor_nombre"),
        },
        "duraciones": {
            "dias_para_resolver": _d("días para resolverlo", "recibido_en", "resuelto_en"),
        },
    },
    "linea_bancaria": {
        "modelo": "contaduria.LineaBancaria",
        "etiqueta": "líneas del estado de cuenta", "etiqueta_singular": "línea del estado de cuenta",
        "genero": "f",
        "campo_fecha": "fecha",
        "link_default": "/contaduria/conciliacion/",
        "campo_autor": None,
        "campo_asignado": None,
        "permiso": ("contaduria.ver",),
        "campos": {
            "monto": _c("monto", "dinero"),
            "conciliada": _c("conciliada", "booleano"),
            "descripcion": _c("descripción", "texto", genero="f"),
            "referencia": _c("referencia", "texto", genero="f"),
            "partida": _c("partida contable", "relacion", genero="f"),
            "fecha": _c("fecha", "fecha", genero="f"),
        },
        "agrupaciones": {
            "conciliada": _g("conciliada", "conciliada"),
            "cuenta": _g("cuenta", "conciliacion__cuenta"),
        },
        "duraciones": {},
    },
    "mandado": {
        "modelo": "pizarron.Mandado",
        "etiqueta": "mandados", "etiqueta_singular": "mandado", "genero": "m",
        "campo_fecha": "creado_en",
        "link_default": "/mandados/",
        "campo_autor": None,
        "campo_asignado": "tarea__runner",
        "permiso": ("pizarron.ver_todos_mandados",),
        "permiso_mio": ("pizarron.ver",),
        "campos": {
            "estado": _c("estado", "opcion"),
            "runner": _c("runner", "relacion", ruta="tarea__runner"),
            "proyecto": _c("proyecto", "relacion", ruta="tarea__proyecto"),
            "distancia_m": _c("distancia en metros", "numero", genero="f"),
            "creado_en": _c("fecha de alta", "fecha", genero="f"),
            "asignado_en": _c("fecha de asignación", "fecha", genero="f"),
            "en_camino_en": _c("salida", "fecha", genero="f"),
            "entregado_en": _c("fecha de entrega", "fecha", genero="f"),
            "cancelado_en": _c("fecha de cancelación", "fecha", genero="f"),
        },
        "agrupaciones": {
            "persona": _g("runner", "tarea__runner"),
            "estado": _g("estado", "estado"),
            "proyecto": _g("proyecto", "tarea__proyecto"),
        },
        "duraciones": {
            "minutos_en_camino": _d("minutos en camino", "en_camino_en", "entregado_en", "minutos"),
            "horas_para_asignar": _d("horas para asignarlo", "creado_en", "asignado_en", "horas"),
        },
    },
}

# Operadores que v1 tenía declarados por campo: v2 debe seguir aceptándolos
# (el candado `test_kpi_dsl_v1_retro` lo prueba con datos).
_OPS_V1: dict[str, dict[str, tuple[str, ...]]] = {
    "proyecto": {"estado": ("eq", "in"), "archivado": ("eq",)},
    "tarea": {"estado": ("eq", "in"), "prioridad": ("eq", "in")},
    "cliente": {"activo": ("eq",), "estado": ("eq", "in")},
    "egreso": {"estado_pago": ("eq", "in"), "metodo": ("eq", "in"), "anulado": ("eq",),
               "descripcion": ("contiene",), "proveedor_nombre": ("contiene", "eq")},
    "ingreso": {"anulado": ("eq",), "descripcion": ("contiene",)},
    "buzon_mensaje": {"tipo": ("eq", "in"), "estado": ("eq", "in")},
}


def ruta_de(entidad: str, campo: str) -> str:
    """El camino del ORM de una llave-campo (sin `ruta`, la llave misma)."""
    spec = ENTIDADES[entidad]["campos"][campo]
    return spec.get("ruta", campo)


def ops_de(entidad: str, campo: str) -> tuple[str, ...]:
    spec = ENTIDADES[entidad]["campos"][campo]
    return tuple(spec.get("ops") or OPS_POR_TIPO[spec["tipo"]])


def _derivar_v1() -> None:
    """Llena `campos_numericos` y `campos_filtrables` (la forma v1) desde
    `campos`, y comprueba que ningún operador v1 se haya perdido."""
    for nombre, cfg in ENTIDADES.items():
        cfg["campos_numericos"] = tuple(
            c for c, s in cfg["campos"].items() if s["tipo"] in TIPOS_AGREGABLES
        )
        cfg["campos_filtrables"] = {c: ops_de(nombre, c) for c in cfg["campos"]}
        cfg.setdefault("permiso_mio", cfg["permiso"])
        for campo, ops in _OPS_V1.get(nombre, {}).items():
            faltan = set(ops) - set(cfg["campos_filtrables"].get(campo, ()))
            if faltan:  # pragma: no cover — sólo si alguien rompe la whitelist
                raise RuntimeError(f"kpi_dsl: {nombre}.{campo} perdió ops v1 {faltan}")


_derivar_v1()

AGREGACIONES = ("count", "sum", "avg", "min", "max")
ETIQUETAS_AGREGACIONES = {
    "count": "número", "sum": "suma", "avg": "promedio", "min": "mínimo", "max": "máximo",
}
# Lo que se puede hacer con una duración (count no: para contar, `count`).
AGREGACIONES_DURACION = ("avg", "min", "max", "sum")

# `contiene` = búsqueda de subcadena case-insensitive (icontains), sólo en
# campos de texto. `vacio` = el campo no tiene valor (valor true) o sí (false).
OPS_FILTRO = ("eq", "in", "gte", "lte", "gt", "lt", "contiene", "vacio")

# Valores especiales de fecha en gt/gte/lt/lte/eq, relativos al día en que se
# calcula el KPI: "hoy", "hace_N_dias", "en_N_dias" (N ≤ MAX_DIAS_RELATIVOS).
VALORES_FECHA_ESPECIALES = ("hoy", "hace_N_dias", "en_N_dias")
MAX_DIAS_RELATIVOS = 3660

# Token → rango de fechas (ejecutor._ventana_a_rango). Las v1 primero.
VENTANAS_TIEMPO = (
    "siempre", "ultimos_7d", "ultimos_30d", "este_mes", "este_ano",
    "esta_semana", "este_trimestre", "mes_pasado", "ultimos_90d", "ultimos_12m",
)
ETIQUETAS_VENTANAS = {
    "siempre": "de siempre",
    "ultimos_7d": "de los últimos 7 días",
    "ultimos_30d": "de los últimos 30 días",
    "ultimos_90d": "de los últimos 90 días",
    "ultimos_12m": "de los últimos 12 meses",
    "esta_semana": "de esta semana",
    "este_mes": "de este mes",
    "mes_pasado": "del mes pasado",
    "este_trimestre": "de este trimestre",
    "este_ano": "de este año",
}

ALCANCES_USUARIO = ("todos", "mio")

TIPOS_KPI = ("valor", "porcentaje")

# Cómo se pinta el número (los mismos de `taller_home.kpi_meta.FORMATOS`).
FORMATOS = ("numero", "dinero", "pct", "dias", "horas", "minutos")
DIRECCIONES = ("sube", "baja", "neutro")
ETIQUETAS_FORMATOS = {
    "numero": "Número", "dinero": "Dinero ($)", "pct": "Porcentaje (%)",
    "dias": "Días", "horas": "Horas", "minutos": "Minutos",
}
ETIQUETAS_DIRECCIONES = {
    "sube": "Más es mejor", "baja": "Menos es mejor", "neutro": "Sólo informa",
}

TOP_GRUPOS_DEFAULT = 10
TOP_GRUPOS_MAX = 50
