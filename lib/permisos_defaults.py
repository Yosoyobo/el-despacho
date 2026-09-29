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
# S-Deuda-Permisos (2026-09-28): las puertas que decidían por ROL pasan a estas
# acciones. Cada una nace con el alcance EXACTO que el rol daba (decisión de
# Oscar: «como hoy» — nadie gana ni pierde). La migración
# `cuentas/0047_permisos_sin_rol_literal` las siembra por usuario.
#   proyectos.ver        → ver los proyectos donde estás asignado
#   proyectos.ver_todos  → ver TODOS los proyectos (antes: super_admin/dueño/contador)
#   proyectos.archivar   → archivar/reactivar proyectos (antes: super_admin/dueño)
TODO_PROYECTOS = ["ver", "ver_todos", "crear", "editar", "asignar", "cambiar_estado", "archivar"]
#   pizarron.ver_comentarios   → leer comentarios de proyectos y tareas
#   pizarron.ver_internos      → leer TODOS los comentarios internos
#   pizarron.comentar_interno  → marcar un comentario como interno
#   pizarron.eliminar          → borrar tareas que creó otra persona
#   pizarron.ver_todos_mandados → ver los mandados de todo el equipo
TODO_PIZARRON = [
    "ver", "crear", "editar", "completar", "ver_internos",
    "ver_comentarios", "comentar_interno", "eliminar", "ver_todos_mandados",
]
#   buzon.eliminar → borrar mensajes de la bandeja de soporte
TODO_BUZON = ["ver_propios", "ver_todos", "responder", "eliminar"]
TODO_RECADOS = ["ver", "crear", "editar_propios", "adjuntar_drive", "ver_historial_todos"]
TODO_TESORERIA = [
    "ver", "capturar_ingreso", "capturar_egreso", "ocr",
    "dictado_gasto", "anular", "reportes", "exportar",
]
TODO_DICTADO = ["crear_proyecto", "actualizar_proyecto", "crear_tarea", "registrar_ingreso", "registrar_egreso"]
# "cargar" (S-Carga-Contable): subir de un jalón la contabilidad llevada fuera.
TODO_CONTADURIA = ["ver", "capturar", "anular", "reportes", "cargar"]
# Pre-S2b.2: el Catálogo se mudó a El Taller con 7 permisos toggleables
# individualmente por super_admin desde /directorio/<id>/permisos/.
TODO_CATALOGO = [
    "ver_nombres", "ver_precios", "crear", "editar", "editar_precios",
    "archivar", "gestionar_categorias",
    # S-LC-Feedback-V13: borrado PERMANENTE de productos/proveedores (≠ archivar).
    # Default solo super_admin (acción destructiva); delegable por usuario.
    "eliminar",
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
# El Análisis (S-Chalan-Analisis): la pantalla donde El Chalán observa y opina
# del negocio. Los TEMAS de adentro ya se gatean uno por uno con su propio
# permiso (finanzas, cotizaciones, cartera…); esto sólo abre la puerta.
TODO_ANALISIS = ["ver"]
# S-Checador: asistencia. `checar` es para todo el staff; las funciones de
# supervisión (ver equipo, aprobar correcciones, configurar horarios,
# exportar) son de admin.
TODO_CHECADOR = ["checar", "ver_equipo", "aprobar_correcciones", "configurar_horarios", "exportar"]
# S-Checador-V2 (2026-09-29): La Nómina interna quincenal de sueldo fijo. Va en
# un módulo propio y no dentro de `checador` porque enseña DINERO de cada
# persona: checar lo trae todo el staff; esto, sólo quien lleva la nómina.
#   ver     → la lista de quincenas, los recibos de todos, el CSV y los PDF
#   editar  → abrir/calcular/recalcular una quincena, editar recibos, préstamos
#   cerrar  → cerrar la quincena (el saldo de los préstamos baja aquí)
#   pagar   → marcar un recibo pagado (salda en Tesorería sus reembolsos)
#   sueldos → capturar y cambiar el sueldo de cada quien
# «Como hoy» (decisión Oscar): nace para super_admin, dueño y contador. La
# migración `checador/0010_seed_permisos_nomina` lo siembra por persona.
# Cada quien ve SUS recibos cerrados sin este permiso (Mi Checador).
TODO_NOMINA = ["ver", "editar", "cerrar", "pagar", "sueldos"]
# V6 Bloque 7: Comunicaciones — correos a clientes vía El Chalán y campañas
# masivas. Default SOLO super_admin (decisión Oscar: gating 100% granular,
# el resto lo recibe vía la grilla de permisos o roles personalizados).
TODO_COMUNICACION = ["enviar_correo", "campanas"]
# S-LC-Proyecto-V2 / S-Roles-V2 (Oscar): El Runner — entregas/recolecciones.
# `recibir` marca a quién puede asignarse como repartidor. YA NO es default de
# ningún rol base: es OPT-IN vía el rol "Runner" (se asigna en
# /directorio/<id>/permisos/). El dropdown de runner solo lista a quien lo tenga;
# si nadie es runner, queda vacío. TODO_RUNNER alimenta el rol "Runner" sembrado
# en la migración cuentas/0033.
TODO_RUNNER = ["recibir"]
# S-Planeador-Rutas: el plan de reparto del día. `ver` es lo que necesita un
# runner para abrir SU ruta; `planear` y `despachar` son de quien organiza la
# vuelta. Se separan porque no es lo mismo consultar la ruta que rearmarla o
# publicarla (y mandarle el correo a alguien).
TODO_RUTAS = ["ver", "planear", "despachar"]
# S-Papeleo-V1: el archivo de papeleo (Paperless). `ver` es buscar y abrir;
# `ligar` es decir de quién es un documento; `subir` es meterlo al archivo.
# Se separan porque leer un contrato y decidir a qué cliente pertenece no
# son la misma responsabilidad.
TODO_PAPELEO = ["ver", "ligar", "subir"]
# S-LC-Feedback-V10 (decisión Oscar: "todo, TODO, debe tener permisos
# granulares"): las áreas administrativas de La Gerencia dejan de gatearse por
# rol literal y pasan a permisos delegables. super_admin sigue como failsafe
# duro en código; los defaults preservan exactamente el alcance previo de cada
# rol. `dueno` mantiene lo que ya alcanzaba (directorio básico, site, interfón,
# lectura de Chalanes); las acciones que eran solo-super_admin se quedan así.
TODO_AJUSTES = ["acceder"]
# `ver` lista · `gestionar` alta/edición básica (lo que el dueño ya tenía) ·
# `panel`/`ia`/`permisos`/`roles` son el panel avanzado de usuario, solo-super_admin.
TODO_DIRECTORIO = ["ver", "gestionar", "panel", "ia", "permisos", "roles"]
TODO_CHALANES = ["ver", "configurar"]
# `api` es el API JSON de El Site (`/api/site/…`). Va aparte de `ver` porque
# hasta S-Deuda-Permisos lo abría el ROL (super_admin/dueño) y no el permiso de la
# pantalla: hay quien tiene uno sin el otro, y «como hoy» obliga a respetarlo.
TODO_SITE = ["ver", "limpiar", "api"]
TODO_CATALOGOS = ["estados", "tipos", "centros_costo"]
TODO_INTERFONO = ["configurar"]
# MCP local: habilita el acceso al servidor; cada herramienta exige además
# el permiso de lectura del módulo de negocio que consulta.
TODO_MCP = ["usar"]
# Sprint de pendientes 2026-09-28 (Oscar): ver quién está en línea y qué está
# haciendo — El Directorio, El Site / El Vigía, Equipo y el Dashboard. «Quién
# ve: todos», así que NACE ACTIVO para cualquier rol y cualquier usuario
# (incluido `miembro`, que no tiene defaults). Sigue siendo granular (§4 #20):
# el super_admin lo revoca por usuario desde /directorio/<id>/permisos/.
TODO_EQUIPO = ["ver_actividad"]
# 2026-09-29 (Oscar): el HISTORIAL de actividad de otros (un año de pantallas y
# acciones) es más sensible que la presencia de ahora, así que NO es universal:
# nace para super_admin y dueño (migración `cuentas/0053`) y se delega por
# persona. El propio historial lo ve cada quien sin permiso.
HISTORIAL_EQUIPO = "ver_historial"
# La Recepción (portal de clientes, S5 2026-09-29): quién ve los accesos de un
# cliente, quién lo invita y quién le quita el acceso. «Como hoy»: lo trae quien
# edita la cartera (super_admin y dueño por default; la migración
# `portal/0002` lo siembra por persona a quien hoy tiene `cartera.editar`).
#   documentos → ver, subir y revisar la papelería que entregan los clientes
#                (comprobantes, CSF, actas). Lo siembra `portal/0006` a quien
#                ya tiene `recepcion.ver`.
TODO_RECEPCION = ["ver", "invitar", "revocar", "documentos"]
# La Caja (links de pago con Stripe y MercadoPago, 2026-09-29). «Como hoy»: la
# recibe quien ya ve el dinero (`tesoreria.ver`) o cobra facturas
# (`facturacion.cobrar`) — la migración `caja/0002_seed_permisos_caja` la siembra.
#   ver          → la pantalla de La Caja, los pagos y el aviso de pago recibido
#   crear_link   → generar el link (factura, anticipo, monto libre) y mandarlo
#   anular_link  → matar un link vigente
#   revisar_pago → decidir un pago que llegó y no cuadró (registrarlo o descartarlo)
TODO_CAJA = ["ver", "crear_link", "anular_link", "revisar_pago"]

# Permisos que nacen activos para TODO usuario sin importar su rol primario.
# `defaults_de()` los suma encima de los del rol, y el signal que siembra a los
# usuarios nuevos pasa por ahí — así un `miembro` recién dado de alta también
# los trae, aunque su rol no tenga fila en DEFAULTS_POR_ROL.
PERMISOS_UNIVERSALES: dict[str, list[str]] = {
    "equipo": list(TODO_EQUIPO),
}


# Las claves de los roles del sistema (para elegir una audiencia por rol en El
# Interfón, p. ej.). Vive aquí y no en `lib.permisos` porque allí ninguna puerta
# puede nombrar un rol (§4 #20).
ROLES_SISTEMA = ("super_admin", "dueno", "contador", "disenador")


DEFAULTS_POR_ROL: dict[str, dict[str, list[str]]] = {
    "super_admin": {
        # "eliminar" (borrado permanente de cliente) SOLO para super_admin
        # (destructivo); `dueno` conserva TODO_CARTERA sin eliminar.
        "cartera": [*TODO_CARTERA, "eliminar"],
        "proyectos": list(TODO_PROYECTOS),
        "pizarron": list(TODO_PIZARRON),
        "buzon": list(TODO_BUZON),
        "recados": list(TODO_RECADOS),
        "tesoreria": list(TODO_TESORERIA),
        "dictado": list(TODO_DICTADO),
        "contaduria": list(TODO_CONTADURIA),
        "catalogo": list(TODO_CATALOGO),
        "cotizaciones": [*TODO_COTIZACIONES, "eliminar"],
        "facturacion": list(TODO_FACTURACION),
        "caja": list(TODO_CAJA),
        "chalan": list(TODO_CHALAN),
        # El Análisis: sólo super_admin por default — enseña dinero de todo el
        # despacho. Se delega por usuario desde El Directorio.
        "analisis": list(TODO_ANALISIS),
        "checador": list(TODO_CHECADOR),
        "nomina": list(TODO_NOMINA),
        "comunicacion": list(TODO_COMUNICACION),
        "rutas": list(TODO_RUTAS),
        "papeleo": list(TODO_PAPELEO),
        # S-LC-Feedback-V5 c5: super_admin entra a La Gerencia por default.
        "gerencia": ["acceder"],
        # S-LC-Feedback-V10: áreas administrativas (super_admin = todo).
        "ajustes": list(TODO_AJUSTES),
        "directorio": list(TODO_DIRECTORIO),
        "chalanes": list(TODO_CHALANES),
        "site": list(TODO_SITE),
        "catalogos": list(TODO_CATALOGOS),
        "interfono": list(TODO_INTERFONO),
        "mcp": list(TODO_MCP),
        "equipo": [*TODO_EQUIPO, HISTORIAL_EQUIPO],
        "recepcion": list(TODO_RECEPCION),
    },
    "dueno": {
        "cartera": list(TODO_CARTERA),
        "proyectos": list(TODO_PROYECTOS),
        "pizarron": list(TODO_PIZARRON),
        # El Buzón de SOPORTE (todos los mensajes, `ver_todos`) es SOLO super_admin
        # por default (decisión Oscar). Sigue siendo granular/delegable: el
        # super_admin puede conceder `ver_todos` a quien quiera desde
        # /directorio/<id>/permisos/. El dueño conserva su propio buzón
        # (`ver_propios` + `responder`), no la bandeja de soporte completa.
        # `eliminar` (borrar de la bandeja de soporte) sí es del dueño; sin
        # `ver_todos` no llega a la bandeja, igual que antes.
        "buzon": ["ver_propios", "responder", "eliminar"],
        "recados": list(TODO_RECADOS),
        "tesoreria": list(TODO_TESORERIA),
        "dictado": list(TODO_DICTADO),
        "contaduria": list(TODO_CONTADURIA),
        # Dueño ve y edita catálogo pero NO gestiona categorías (decisión Pre-S2b.2).
        "catalogo": ["ver_nombres", "ver_precios", "crear", "editar", "editar_precios", "archivar"],
        "cotizaciones": list(TODO_COTIZACIONES),
        "facturacion": list(TODO_FACTURACION),
        "caja": list(TODO_CAJA),
        "chalan": list(TODO_CHALAN),
        "checador": list(TODO_CHECADOR),
        "nomina": list(TODO_NOMINA),
        # S-LC-Feedback-V5 c5: dueno entra a La Gerencia por default.
        "gerencia": ["acceder"],
        # S-LC-Feedback-V10: dueno conserva exactamente lo que ya alcanzaba —
        # directorio (lista + alta/edición de usuarios), El Site, El Interfón y
        # lectura del panel de Chalanes. IA/permisos/roles y Los Ajustes siguen
        # siendo solo-super_admin.
        "directorio": ["ver", "gestionar"],
        "chalanes": ["ver"],
        "site": list(TODO_SITE),
        "interfono": list(TODO_INTERFONO),
        "equipo": [*TODO_EQUIPO, HISTORIAL_EQUIPO],
        "recepcion": list(TODO_RECEPCION),
    },
    "contador": {
        # Contador ve cartera read-only; no edita proyectos ni pizarrón.
        "cartera": ["ver"],
        # Contador ve TODOS los proyectos (para reconciliar pagos), no edita.
        "proyectos": ["ver", "ver_todos"],
        # Lee todos los comentarios (también los internos) y puede escribir
        # internos — así era por su rol PRIMARIO (ver la migración 0047).
        "pizarron": ["ver", "ver_comentarios", "ver_internos", "comentar_interno"],
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
        "caja": list(TODO_CAJA),
        "chalan": list(TODO_CHALAN),
        # Contador checa, ve al equipo y exporta (insumo para nómina/costos);
        # no aprueba correcciones ni configura horarios.
        "checador": ["checar", "ver_equipo", "exportar"],
        # El contador lleva la nómina (la captura y la cierra) — decisión Oscar.
        "nomina": list(TODO_NOMINA),
        "equipo": list(TODO_EQUIPO),
    },
    "disenador": {
        # Diseñador NO ve cartera (DOC_01 §4.4).
        # Sólo ve los proyectos donde está asignado (`ver` sin `ver_todos`).
        # S-Deuda-Permisos: traía `editar` «sólo donde asignado», pero la puerta
        # era el ROL y nunca le dejó editar nada. Se le quita para que el
        # permiso no mienta (decisión Oscar: «como hoy»).
        "proyectos": ["ver"],
        "pizarron": ["ver", "crear", "editar", "completar", "ver_comentarios"],
        "buzon": ["ver_propios", "responder"],
        "recados": ["ver", "crear", "editar_propios", "adjuntar_drive"],
        "dictado": ["actualizar_proyecto", "crear_tarea"],
        # Diseñador ve nombres pero NO precios (default — toggleable individualmente).
        "catalogo": ["ver_nombres"],
        "chalan": list(TODO_CHALAN),
        # Diseñador solo checa su propia jornada/visitas/tiempo.
        "checador": ["checar"],
        "equipo": list(TODO_EQUIPO),
    },
}


# Catálogo canónico módulo→acciones. FUENTE ÚNICA para los editores de permisos
# (grilla del form de Rol y grilla por-usuario). Incluye TODAS las acciones de
# cada módulo — independiente del rol primario, para poder conceder cualquier
# permiso a cualquier usuario (incluido `miembro`, que no tiene defaults).
CATALOGO_PERMISOS: dict[str, list[str]] = {
    # "eliminar" (borrado permanente de cliente archivado) NO está en TODO_CARTERA
    # a propósito: destructivo, solo super_admin lo trae por default (failsafe) +
    # delegable por usuario. Se lista aquí para que aparezca en la grilla.
    "cartera": [*TODO_CARTERA, "eliminar"],
    "proyectos": list(TODO_PROYECTOS),
    "pizarron": list(TODO_PIZARRON),
    "buzon": list(TODO_BUZON),
    "recados": list(TODO_RECADOS),
    "tesoreria": list(TODO_TESORERIA),
    "dictado": list(TODO_DICTADO),
    "contaduria": list(TODO_CONTADURIA),
    "catalogo": list(TODO_CATALOGO),
    # "eliminar" (borrado permanente de una cotización anulada o en borrador) NO
    # está en TODO_COTIZACIONES a propósito: destructivo, solo super_admin lo trae
    # por default (failsafe) + delegable por usuario.
    "cotizaciones": [*TODO_COTIZACIONES, "eliminar"],
    "facturacion": list(TODO_FACTURACION),
    # La Caja: links de pago y pagos en línea.
    "caja": list(TODO_CAJA),
    "chalan": list(TODO_CHALAN),
    # El Análisis nació (S-Chalan-Analisis) en `DEFAULTS_POR_ROL` pero no aquí,
    # así que no aparecía en `/directorio/<id>/permisos/` y NO se podía delegar
    # a nadie más que al super_admin — lo contrario de lo acordado. Cazado en
    # S-Deuda-Sep28 por el candado que cruza los dos diccionarios.
    "analisis": list(TODO_ANALISIS),
    "checador": list(TODO_CHECADOR),
    # La Nómina interna (sueldos, quincenas, recibos, préstamos).
    "nomina": list(TODO_NOMINA),
    "comunicacion": list(TODO_COMUNICACION),
    # runner: ya no es default de ningún rol; se concede vía el rol "Runner"
    # (opt-in). Permanece en el catálogo para poder marcarlo en el editor de roles.
    "runner": list(TODO_RUNNER),
    # rutas: super_admin las trae por default; el runner recibe `ver` desde el
    # rol "Runner" (opt-in, ver la migración de este sprint).
    "rutas": list(TODO_RUTAS),
    # papeleo: super_admin lo trae; el resto se delega desde El Directorio.
    "papeleo": list(TODO_PAPELEO),
    "gerencia": ["acceder"],
    # S-LC-Feedback-V10: áreas administrativas de La Gerencia, delegables.
    "ajustes": list(TODO_AJUSTES),
    "directorio": list(TODO_DIRECTORIO),
    "chalanes": list(TODO_CHALANES),
    "site": list(TODO_SITE),
    "catalogos": list(TODO_CATALOGOS),
    "interfono": list(TODO_INTERFONO),
    "mcp": list(TODO_MCP),
    # Ver quién está en línea y su última actividad (nace activo para todos) y el
    # historial de un año de otros (sólo super_admin y dueño por default).
    "equipo": [*TODO_EQUIPO, HISTORIAL_EQUIPO],
    # La Recepción: ver / invitar / revocar el acceso de un cliente al portal.
    "recepcion": list(TODO_RECEPCION),
}


def defaults_de(rol: str) -> dict[str, list[str]]:
    """Devuelve dict {modulo: [permisos]} para un rol, más los universales.

    Un rol desconocido (o `miembro`, que no tiene defaults a propósito) recibe
    sólo `PERMISOS_UNIVERSALES`: lo que TODO usuario trae desde que nace.
    """
    return con_universales(DEFAULTS_POR_ROL.get(rol, {}))


def con_universales(permisos: dict | None) -> dict[str, list[str]]:
    """El JSON de un rol con `PERMISOS_UNIVERSALES` sumados (sin repetir).

    Lo usa el alta de roles: todo usuario trae los universales por su fila
    individual, así que un rol que naciera sin ellos haría mentir a «ver como
    rol» (que evalúa SÓLO el JSON del rol simulado). Se revocan por persona,
    no por rol (`cuentas/0046`)."""
    base = {m: list(a) for m, a in (permisos or {}).items()}
    for modulo, acciones in PERMISOS_UNIVERSALES.items():
        actuales = base.setdefault(modulo, [])
        for accion in acciones:
            if accion not in actuales:
                actuales.append(accion)
    return base


def catalogo_permisos() -> dict[str, list[str]]:
    """Catálogo canónico módulo→[acciones] — todas las acciones de cada módulo."""
    return {m: list(a) for m, a in CATALOGO_PERMISOS.items()}
