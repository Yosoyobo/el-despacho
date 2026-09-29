"""Permisos centralizados — `puede()`, decoradores y helpers.

Regla §4 #20: toda puerta pregunta por un permiso GRANULAR (`modulo.accion` del
catálogo de `lib.permisos_defaults`), nunca por el nombre de un rol. El único rol
que decide algo por sí mismo es `super_admin`, el failsafe anti lock-out
(`es_super_admin`). `tests/test_permisos_sin_rol_literal.py` falla si reaparece
otro nombre de rol en este archivo.

Los roles siguen existiendo —son paquetes de permisos que se asignan desde El
Directorio— y este módulo sabe resolverlos (`roles_efectivos`, `tiene_rol`),
pero ninguna puerta de aquí los usa para decidir.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, HttpResponseForbidden
from django.shortcuts import redirect


def roles_efectivos(user) -> set[str]:
    """S-LC-Feedback-V5 c7 / fix: unión del rol primario (`user.rol`) +
    los nombres de los `roles_extra` asignados.

    Es la base de los checks que gatean por **nombre de rol** (no por
    permiso granular). Sin esto los roles extra solo aplicaban al camino
    granular `puede()` y los helpers gruesos (`es_admin`,
    `puede_ver_finanzas`, etc.) los ignoraban — por eso "los roles no se
    aplicaban" al asignarlos. Defensivo: si el M2M no existe (modelo viejo
    o usuario sin guardar) devuelve solo el rol primario."""
    # S-Roles-V2: "ver como rol" (debug/QA). Si el middleware marcó un rol
    # simulado, el usuario se comporta COMO SI solo tuviera ese rol.
    sim = getattr(user, "_rol_simulado", None)
    if sim:
        return {sim}
    roles: set[str] = set()
    primario = getattr(user, "rol", None)
    if primario:
        roles.add(primario)
    # S-Mandados-V2: la identidad de un rol es su `clave` estable (no el `nombre`,
    # que el usuario puede renombrar libremente). Todos los checks por nombre de
    # rol comparan claves.
    with contextlib.suppress(Exception):
        roles.update(user.roles_extra.values_list("clave", flat=True))
    return roles


def roles_display(user) -> list[str]:
    """S-LC-Feedback-V9 — lista LEGIBLE de roles para la ficha del usuario:
    la etiqueta del rol primario (`get_rol_display`) + los nombres de los roles
    personalizados (`roles_extra`). Evita mostrar slugs crudos como
    "super_admin". Defensivo: nunca lanza."""
    out: list[str] = []
    try:
        primario = user.get_rol_display()
    except Exception:  # noqa: BLE001
        primario = getattr(user, "rol", "") or ""
    if primario:
        out.append(primario)
    with contextlib.suppress(Exception):
        out.extend(sorted(user.roles_extra.values_list("nombre", flat=True)))
    return out


def tiene_rol(user, *nombres: str) -> bool:
    """V6 Bloque 10: check canónico por NOMBRE de rol. Reconoce tanto el rol
    primario como los roles personalizados (roles_extra). Reemplaza a los
    `user.rol == "x"` / `user.rol in (...)` directos."""
    return bool(roles_efectivos(user) & set(nombres))


def usuarios_con_rol(*nombres: str):
    """Queryset de usuarios activos cuyo rol primario O alguno de sus roles
    personalizados está en `nombres`. Para destinatarios de pushes/avisos."""
    from django.db.models import Q

    from cuentas.models.usuario import Usuario
    return Usuario.objects.filter(
        Q(rol__in=nombres) | Q(roles_extra__clave__in=nombres),
        is_active=True,
    ).distinct()


def sincronizar_rol_primario(user) -> str:
    """S-Roles-V2: tras unificar roles en UN solo selector (los roles asignados,
    `roles_extra`), `Usuario.rol` se DERIVA de ese set — ya no se edita con un
    dropdown aparte. super_admin si tiene ese rol; si no, miembro. Sincroniza
    is_staff/is_superuser (failsafe + Django admin). Es el único punto que escribe
    `Usuario.rol`. Devuelve el rol derivado."""
    tiene_sa = False
    with contextlib.suppress(Exception):
        tiene_sa = user.roles_extra.filter(clave="super_admin").exists()
    nuevo = "super_admin" if tiene_sa else "miembro"
    user.rol = nuevo
    user.is_staff = tiene_sa
    user.is_superuser = tiene_sa
    user.save(update_fields=["rol", "is_staff", "is_superuser"])
    return nuevo


def es_super_admin(user) -> bool:
    """El failsafe duro (§4 #20): el ÚNICO rol que decide algo por sí mismo."""
    return "super_admin" in roles_efectivos(user)


def puede_ver_ajustes(user) -> bool:
    return es_super_admin(user)


# ── Puertas que antes decidían por ROL (S-Deuda-Permisos, 2026-09-28) ─────────
#
# Hasta aquí vivían `es_admin` (super_admin|dueño), `puede_ver_finanzas`
# (super_admin|dueño|contador) y compañía: leían el NOMBRE del rol, así que no se
# podían delegar desde El Directorio. Ahora cada una pregunta por una acción del
# catálogo. Decisión de Oscar: «como hoy» — la migración
# `cuentas/0047_permisos_sin_rol_literal` sembró cada acción exactamente a quien
# el rol ya se la daba, y `tests/test_permisos_sin_rol_literal.py` compara, rol
# por rol, la decisión vieja (copiada ahí, congelada) contra la nueva.
#
# `super_admin` sigue siendo failsafe en cada una: `puede()` no lo tiene.


def puede_ver_todos_proyectos(user) -> bool:
    """Ver TODOS los proyectos, no sólo aquellos donde uno está asignado.

    Antes: super_admin/dueño/contador (el contador, para reconciliar pagos).
    También abre todas las tareas del Pizarrón y el calendario completo.
    """
    return es_super_admin(user) or puede(user, "proyectos", "ver_todos")


def puede_ver_proyectos_asignados(user) -> bool:
    """Ver al menos los proyectos donde uno está asignado (antes: cualquiera de
    los cuatro roles del sistema). Quien no lo tiene no ve proyectos."""
    return puede_ver_todos_proyectos(user) or puede(user, "proyectos", "ver")


def solo_proyectos_asignados(user) -> bool:
    """¿Hay que acotar a este usuario a SUS proyectos?

    Es la vieja condición «diseñador sin un rol amplio»: ve proyectos, pero no
    todos. Ojo, a propósito como hoy: quien no tiene NINGÚN permiso de
    proyectos no entra en esta condición (las pantallas que la usan ya lo
    filtran por su cuenta o nunca lo acotaron).
    """
    return not puede_ver_todos_proyectos(user) and puede(user, "proyectos", "ver")


def puede_ver_proyecto(user, proyecto) -> bool:
    if puede_ver_todos_proyectos(user):
        return True
    if puede(user, "proyectos", "ver"):
        return proyecto.asignaciones.filter(usuario_id=user.pk).exists()
    return False


def puede_gestionar_proyectos(user) -> bool:
    """Editar proyectos (`proyectos.editar`): datos, productos, fechas, dinero.

    Antes: super_admin/dueño. El diseñador traía `editar` en sus defaults «sólo
    donde asignado», pero la puerta era el rol y nunca editó nada; se le quitó
    (decisión Oscar: «como hoy»). También abre la actividad de TODOS los
    proyectos en Recados — quien los gestiona ve lo que pasa en ellos.

    Crear, asignar y cambiar de estado tienen su propia acción desde
    2026-09-28 (`puede_crear_proyecto`, `puede_asignar_proyecto`,
    `puede_cambiar_estado_proyecto`); hasta entonces las tres usaban ésta.
    """
    return es_super_admin(user) or puede(user, "proyectos", "editar")


def puede_editar_proyecto(user, proyecto) -> bool:
    """Mutar un proyecto. No depende del proyecto: quien gestiona proyectos los
    gestiona todos. (Crearlo es `puede_crear_proyecto`.)"""
    return puede_gestionar_proyectos(user)


# `proyectos.crear/asignar/cambiar_estado` estaban en el catálogo pero ninguna
# puerta las leía: todo pasaba por `editar`. Se conectaron «como hoy»: la
# migración `cuentas/0048` sembró cada una, por persona, a exactamente quien
# tenía `editar` efectivo (y la apagó a quien la traía sin él).


def puede_crear_proyecto(user) -> bool:
    """Crear proyectos: el alta, duplicar uno existente, y El Chalán
    (`crear_proyecto`, `duplicar_proyecto`)."""
    return es_super_admin(user) or puede(user, "proyectos", "crear")


def puede_asignar_proyecto(user) -> bool:
    """Decidir quién trabaja en un proyecto: la pantalla de asignar, el equipo
    del detalle y El Chalán (`asignar_usuario_proyecto`)."""
    return es_super_admin(user) or puede(user, "proyectos", "asignar")


def puede_cambiar_estado_proyecto(user) -> bool:
    """Mover un proyecto por su ciclo (barra de status, Kanban, «¿pasar a
    Esperando respuesta?», motivo de cancelación) y El Chalán cuando
    `actualizar_proyecto` trae un `estado`."""
    return es_super_admin(user) or puede(user, "proyectos", "cambiar_estado")


def puede_archivar_proyecto(user) -> bool:
    """Archivar/reactivar proyectos (ocultar de prueba/duplicados).
    Distinto de «Cancelado» (estado real del ciclo). Antes: super_admin/dueño."""
    return es_super_admin(user) or puede(user, "proyectos", "archivar")


def puede_eliminar_proyecto(user) -> bool:
    """Borrado PERMANENTE de un proyecto: solo super_admin (failsafe), y la
    vista además exige que no tenga movimientos financieros ligados (LC 2026-07)."""
    return es_super_admin(user)


def puede_ver_cartera(user) -> bool:
    """Listar y ver clientes. Antes: super_admin/dueño/contador."""
    return es_super_admin(user) or puede(user, "cartera", "ver")


def puede_editar_cartera(user) -> bool:
    """Crear/editar/archivar clientes. Antes: super_admin/dueño."""
    return es_super_admin(user) or puede(user, "cartera", "editar")


def puede_ver_finanzas(user) -> bool:
    """Ver el dinero del despacho: La Tesorería y todo lo que enseña montos
    (anticipos, rentabilidad, proveedores, gasto de IA…). Es `tesoreria.ver`:
    antes la Tesorería misma se abría con este helper por ROL
    (super_admin/dueño/contador) mientras sus CFDI ya pedían `tesoreria.ver`.
    """
    return es_super_admin(user) or puede(user, "tesoreria", "ver")


def puede_comentar_interno(user) -> bool:
    """Marcar un comentario como interno. Antes: super_admin/dueño o el rol
    PRIMARIO contador (la vista leía `user.rol`)."""
    return es_super_admin(user) or puede(user, "pizarron", "comentar_interno")


def puede_eliminar_tarea(user, tarea) -> bool:
    """Borrar para siempre una tarea: quien la creó, o quien tiene
    `pizarron.eliminar` (antes: super_admin/dueño)."""
    if tarea is not None and tarea.creado_por_id == getattr(user, "pk", None):
        return True
    return es_super_admin(user) or puede(user, "pizarron", "eliminar")


def puede_ver_todos_mandados(user) -> bool:
    """Ver los mandados de todo el equipo, no sólo los propios. Antes:
    super_admin/dueño (el contador ve todas las TAREAS, pero sus mandados no)."""
    return es_super_admin(user) or puede(user, "pizarron", "ver_todos_mandados")


def puede_eliminar_buzon(user) -> bool:
    """Borrar mensajes de la bandeja de soporte (además de `buzon.ver_todos`
    para llegar a ella). Antes: super_admin/dueño."""
    return es_super_admin(user) or puede(user, "buzon", "eliminar")


def puede_usar_api_site(user) -> bool:
    """El API JSON de El Site (`/api/site/…`). Antes: super_admin/dueño."""
    return es_super_admin(user) or puede(user, "site", "api")


def puede_acceder_gerencia(user) -> bool:
    """Entrar a La Gerencia (y lo que va con ella: su tablero, refrescar la
    caché de Novedades). super_admin siempre."""
    return es_super_admin(user) or puede(user, "gerencia", "acceder")


def puede_consultar_saldo_chalanes(user) -> bool:
    """Consultar el saldo de un proveedor de IA. Es `chalanes.ver`, lo mismo que
    pide la pantalla de Los Chalanes en La Gerencia. Antes, en El Taller:
    super_admin/dueño."""
    return es_super_admin(user) or puede(user, "chalanes", "ver")


def puede_eliminar_cartera(user) -> bool:
    """Borrado PERMANENTE de un cliente archivado (destructivo). Por default solo
    super_admin (failsafe); delegable por usuario desde /directorio/."""
    return puede(user, "cartera", "eliminar")


def puede_eliminar_cotizaciones(user) -> bool:
    """Borrado PERMANENTE de una cotización anulada o en borrador (destructivo).

    LC 2026-07-25: sin esto, una cotización anulada dejaba al cliente archivado
    imposible de eliminar (`Cotizacion.cliente` es PROTECT). Por default solo
    super_admin; delegable por usuario desde /directorio/.
    """
    return puede(user, "cotizaciones", "eliminar")


def puede_ver_catalogo(user) -> bool:
    """Ver el Catálogo (productos y proveedores): la acción es `ver_nombres`.

    Hasta S-Deuda-Sep28 preguntaba por `catalogo.ver`, una acción que NO existe
    en `CATALOGO_PERMISOS` (las del módulo son `ver_nombres` / `ver_precios`),
    así que devolvía False para todo el mundo, super_admin incluido. Nadie la
    usaba y por eso no se notó; quien la hubiera usado habría escondido el
    Catálogo sin que nada lo dijera. `test_deuda_sep28` revisa que cada
    `puede(…, "modulo", "accion")` literal de este archivo exista en el catálogo.
    """
    return puede(user, "catalogo", "ver_nombres")


def puede_crear_catalogo(user) -> bool:
    """Crear servicios/variaciones/proveedores del Catálogo (mismo permiso que
    el botón 'Nuevo' de la UI). Lo usa El Chalán para crear productos."""
    return puede(user, "catalogo", "crear")


def puede_editar_catalogo(user) -> bool:
    """Editar productos del Catálogo (mismo permiso que el botón 'Editar' de la
    UI). Lo usa El Chalán para actualizar precio/costo/nombre (LC #153)."""
    return puede(user, "catalogo", "editar")


def puede_eliminar_catalogo(user) -> bool:
    """Borrado PERMANENTE de productos/proveedores (≠ archivar). Acción
    destructiva — default solo super_admin (S-LC-Feedback-V13)."""
    return puede(user, "catalogo", "eliminar")


def puede_editar_proveedores(user) -> bool:
    """Editar la ficha de un proveedor. La pantalla (alta, edición y ficha en
    línea) la gatea con `catalogo.gestionar_categorias`, no con `editar`, así
    que El Chalán pide lo mismo: lo que no se puede con clicks no se puede
    dictando (sprint de pendientes 2026-09-28)."""
    return puede(user, "catalogo", "gestionar_categorias")


def puede_ver_tarea(user, tarea) -> bool:
    """Tareas: heredan la visibilidad del proyecto."""
    return puede_ver_proyecto(user, tarea.proyecto)


def puede_ver_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "ver")


def puede_crear_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "crear")


def puede_editar_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "editar")


def puede_enviar_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "enviar")


def puede_aprobar_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "aprobar")


def puede_rechazar_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "rechazar")


def puede_anular_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "anular")


def puede_ver_facturacion(user) -> bool:
    return puede(user, "facturacion", "ver")


def puede_crear_facturacion(user) -> bool:
    return puede(user, "facturacion", "crear")


def puede_editar_facturacion(user) -> bool:
    return puede(user, "facturacion", "editar")


def puede_emitir_facturacion(user) -> bool:
    return puede(user, "facturacion", "emitir")


def puede_cobrar_facturacion(user) -> bool:
    return puede(user, "facturacion", "cobrar")


def puede_cancelar_facturacion(user) -> bool:
    return puede(user, "facturacion", "cancelar")


def puede_ver_contaduria(user) -> bool:
    return puede(user, "contaduria", "ver")


def puede_capturar_contaduria(user) -> bool:
    return puede(user, "contaduria", "capturar")


def puede_cargar_contaduria(user) -> bool:
    """Subir la plantilla de carga contable (S-Carga-Contable). Aplicarla mueve
    saldos de todo el libro: acción aparte de `capturar` para poder delegarla sola."""
    return puede(user, "contaduria", "cargar")


def puede_anular_contaduria(user) -> bool:
    return puede(user, "contaduria", "anular")


def puede_reportes_contaduria(user) -> bool:
    return puede(user, "contaduria", "reportes")


# V6 Bloque 7 — Comunicaciones (correo a clientes vía Chalán + campañas).
def puede_enviar_correo(user) -> bool:
    return puede(user, "comunicacion", "enviar_correo")


def puede_campanas(user) -> bool:
    return puede(user, "comunicacion", "campanas")


def puede_usar_chalan(user) -> bool:
    """S-Estados-Color-HEX: acceso al chat conversacional de El Chalán."""
    return puede(user, "chalan", "usar")


def puede_limpiar_site(user) -> bool:
    """Correr La Limpieza (soltar caché, RAM y disco) desde El Site.

    Va aparte de `site.ver` porque MUEVE la máquina —recicla los trabajadores de
    gunicorn, aspira la base, poda lo que Docker dejó tirado— y ver el tablero no
    tiene por qué implicar poder tocarlo. En la pared del NUC no se consulta: ahí
    la puerta es estar físicamente en la máquina.
    """
    return puede(user, "site", "limpiar")


def puede_ver_analisis(user) -> bool:
    """Entrar a El Análisis. Los temas de adentro se gatean uno por uno."""
    return puede(user, "analisis", "ver")


def puede_checar(user) -> bool:
    """S-Checador: registrar jornada/visitas/tiempo (todo el staff por default)."""
    return puede(user, "checador", "checar")


def puede_ser_runner(user) -> bool:
    """S-LC-Proyecto-V2: elegible para recibir entregas/recolecciones (runner)."""
    return puede(user, "runner", "recibir")


def puede_acceder_ajustes(user) -> bool:
    """Entrar a la configuración del despacho.

    Es el permiso con el que se gatean también las automatizaciones (n8n): una
    automatización prendida le manda correos a clientes, así que tocarlas es
    tocar la configuración del despacho, no una operación del día a día.
    """
    return puede(user, "ajustes", "acceder")


def puede_ver_rutas(user) -> bool:
    """Abrir el planeador y ver las rutas del día."""
    return puede(user, "rutas", "ver")


def puede_planear_rutas(user) -> bool:
    """Armar o rearmar el reparto del día, y mover paradas entre runners."""
    return puede(user, "rutas", "planear")


def puede_despachar_rutas(user) -> bool:
    """Publicar una ruta — es lo que le manda el correo al runner."""
    return puede(user, "rutas", "despachar")


def puede_ver_papeleo(user) -> bool:
    """Buscar en el archivo y abrir un documento."""
    return puede(user, "papeleo", "ver")


def puede_ver_actividad_equipo(user) -> bool:
    """Ver quién está en línea y en qué pantalla anda cada quien (El Directorio,
    El Site / El Vigía, Equipo y el Dashboard). Nace activo para todos — decisión
    de Oscar, 2026-09-28: «quién ve: todos» — pero sigue siendo granular: se
    revoca por usuario desde El Directorio (§4 #20)."""
    return puede(user, "equipo", "ver_actividad")


def puede_ver_historial_equipo(user) -> bool:
    """Ver el historial de actividad de OTRAS personas (un año de pantallas y
    acciones). Nace para super_admin y dueño; se delega por persona (§4 #20)."""
    return puede(user, "equipo", "ver_historial")


def puede_ver_historial_de(viewer, persona) -> bool:
    """El propio historial lo ve cada quien; el de otro, con el permiso."""
    if not viewer or not getattr(viewer, "is_authenticated", False):
        return False
    if persona is not None and getattr(persona, "pk", persona) == viewer.pk:
        return True
    return puede_ver_historial_equipo(viewer)


def puede_ligar_papeleo(user) -> bool:
    """Decir de qué cliente, proyecto o proveedor es un documento."""
    return puede(user, "papeleo", "ligar")


def puede_subir_papeleo(user) -> bool:
    """Mandar un archivo al archivo del papeleo."""
    return puede(user, "papeleo", "subir")


def puede_ver_accesos_portal(user) -> bool:
    """Ver quién de un cliente puede entrar a La Recepción (portal de clientes)."""
    return puede(user, "recepcion", "ver")


def puede_invitar_portal(user) -> bool:
    """Mandarle a un contacto del cliente su invitación a La Recepción."""
    return puede(user, "recepcion", "invitar")


def puede_revocar_portal(user) -> bool:
    """Quitarle a alguien el acceso a La Recepción (cierra su sesión viva)."""
    return puede(user, "recepcion", "revocar")


def puede_documentos_portal(user) -> bool:
    """Ver, subir y revisar la papelería que entregan los clientes (comprobantes,
    constancia fiscal, actas). Es delicada: un acta trae datos de los socios."""
    return puede(user, "recepcion", "documentos")
def puede_ver_caja(user) -> bool:
    """La Caja: links de pago y los pagos que llegaron por Stripe/MercadoPago."""
    return puede(user, "caja", "ver")


def puede_crear_link_caja(user) -> bool:
    """Generar un link de pago (factura, anticipo o monto libre) y mandarlo."""
    return puede(user, "caja", "crear_link")


def puede_anular_link_caja(user) -> bool:
    """Anular un link de pago vigente."""
    return puede(user, "caja", "anular_link")


def puede_revisar_pago_caja(user) -> bool:
    """Decidir un pago que llegó y no cuadró: registrarlo o descartarlo."""
    return puede(user, "caja", "revisar_pago")


def usuarios_con_permiso(modulo: str, accion: str) -> list:
    """Usuarios activos que tienen `(modulo, accion)` — por fila propia o por
    cualquiera de sus roles.

    Existe para los avisos que se reparten «a quien puede ver X» (§4 #20: nada
    por rol literal). Pasa por `puede()` usuario por usuario a propósito: es la
    ÚNICA definición de quién tiene un permiso, con su precedencia (una fila
    individual apagada revoca aunque el rol lo dé). Un filtro en SQL que la
    imitara acabaría disintiendo de ella en el primer caso raro. Con los pocos
    usuarios del despacho, recorrerlos cuesta nada.
    """
    from cuentas.models.usuario import Usuario

    return [u for u in Usuario.objects.filter(is_active=True).order_by("pk")
            if puede(u, modulo, accion)]


def usuarios_runner():
    """Usuarios activos elegibles como runner — permiso (runner, recibir).

    S-Roles-V2 (Oscar): runner dejó de ser default; es OPT-IN vía el rol
    "Runner". SIN fallback: si nadie es runner, devuelve lista vacía (el dropdown
    de asignación queda sin gente y la auto-asignación no encuentra candidato,
    que es el comportamiento correcto). La elegibilidad se cura asignando el rol
    "Runner" desde /directorio/<id>/permisos/."""
    from cuentas.models.usuario import Usuario
    activos = Usuario.objects.filter(is_active=True).order_by("nombre_completo")
    return [u for u in activos if puede_ser_runner(u)]


def puede_ver_equipo_checador(user) -> bool:
    return puede(user, "checador", "ver_equipo")


def puede_aprobar_correcciones_checador(user) -> bool:
    return puede(user, "checador", "aprobar_correcciones")


def puede_configurar_horarios_checador(user) -> bool:
    return puede(user, "checador", "configurar_horarios")


def puede_aprobar_correccion_de(admin, empleado) -> bool:
    """S-LC-Feedback-V7 — gobernanza de ajustes de horas por jefe directo.

    Sólo aprueba los ajustes de `empleado` quien sea:
      • su `jefe_directo` (con permiso de aprobar correcciones), o
      • super_admin (failsafe duro, siempre puede).
    Nunca uno mismo (eso lo bloquea `resolver_correccion`).
    """
    if admin is None or empleado is None:
        return False
    if tiene_rol(admin, "super_admin"):
        return True
    if not puede_aprobar_correcciones_checador(admin):
        return False
    return getattr(empleado, "jefe_directo_id", None) == getattr(admin, "pk", None)


def puede_ver_horas_trabajadas_de(viewer, empleado) -> bool:
    """S-LC-Feedback-V9 — privacidad de horas trabajadas (decisión Oscar).

    Las HORAS TRABAJADAS (jornadas, retardos, tiempo de proyecto) de un empleado
    solo las ve:
      • el propio empleado,
      • su `jefe_directo`, o
      • super_admin (failsafe duro).
    Cualquier otro (incluidos admins que no son su jefe) solo ve el HORARIO
    DECLARADO de la semana — nunca las horas reales. El permiso `ver_equipo` da
    acceso al reporte del Checador, pero NO a las horas de quien no es tu
    subordinado directo."""
    if viewer is None or empleado is None:
        return False
    if getattr(viewer, "pk", None) == getattr(empleado, "pk", None):
        return True
    if tiene_rol(viewer, "super_admin"):
        return True
    return getattr(empleado, "jefe_directo_id", None) == getattr(viewer, "pk", None)


def puede_exportar_checador(user) -> bool:
    return puede(user, "checador", "exportar")


# ── La Nómina interna (S-Checador-V2, 2026-09-29) ─────────────────────────────
# Módulo `documentos` (La Imprenta), sembrado «como hoy» por
# `imprenta/0002_seed_permisos_documentos`: quien entraba a Ajustes → Documentos.

def puede_ver_compras(user) -> bool:
    return es_super_admin(user) or puede(user, "compras", "ver")


def puede_crear_compras(user) -> bool:
    return es_super_admin(user) or puede(user, "compras", "crear")


def puede_editar_compras(user) -> bool:
    return es_super_admin(user) or puede(user, "compras", "editar")


def puede_cancelar_compras(user) -> bool:
    return es_super_admin(user) or puede(user, "compras", "cancelar")


def puede_ver_documentos(user) -> bool:
    return es_super_admin(user) or puede(user, "documentos", "ver")


def puede_editar_estilo_documentos(user) -> bool:
    return es_super_admin(user) or puede(user, "documentos", "editar_estilo")


def puede_editar_notas_documentos(user) -> bool:
    return es_super_admin(user) or puede(user, "documentos", "editar_notas")


def puede_editar_datos_documentos(user) -> bool:
    return es_super_admin(user) or puede(user, "documentos", "editar_datos")


# Módulo `nomina`, sembrado «como hoy» por `checador/0010_seed_permisos_nomina`.
# Nadie ve montos de otros sin `nomina.ver`; cada quien ve SUS recibos cerrados
# (eso no pasa por aquí: lo decide `puede_ver_recibo`).


def puede_ver_nomina(user) -> bool:
    return es_super_admin(user) or puede(user, "nomina", "ver")


def puede_editar_nomina(user) -> bool:
    """Abrir, calcular y recalcular una quincena; editar recibos y préstamos."""
    return es_super_admin(user) or puede(user, "nomina", "editar")


def puede_cerrar_nomina(user) -> bool:
    return es_super_admin(user) or puede(user, "nomina", "cerrar")


def puede_pagar_nomina(user) -> bool:
    """Marcar un recibo pagado (y saldar en Tesorería sus reembolsos)."""
    return es_super_admin(user) or puede(user, "nomina", "pagar")


def puede_capturar_sueldos(user) -> bool:
    return es_super_admin(user) or puede(user, "nomina", "sueldos")


def puede_ver_recibo(user, recibo) -> bool:
    """El candado del recibo: quien lleva la nómina ve todos; la persona, sólo
    los SUYOS y sólo cuando la quincena ya se cerró."""
    if user is None or recibo is None or not getattr(user, "is_authenticated", False):
        return False
    if puede_ver_nomina(user):
        return True
    return recibo.usuario_id == user.pk and recibo.periodo.estado == "cerrado"


def puede_ver_comentario(user, comentario) -> bool:
    """¿Este usuario lee este comentario de proyecto o tarea?

    - sin `pizarron.ver_comentarios` no lee ninguno;
    - con `pizarron.ver_internos` los lee todos;
    - si no, lee los públicos —y los internos que él escribió— de los
      proyectos que ve.

    Hasta S-Deuda-Permisos esto se decidía por el rol PRIMARIO (`user.rol`), no
    por los roles efectivos como todo lo demás: quien tiene un rol ASIGNADO
    (p. ej. «Director» sobre un rol primario `miembro`) no leía ningún
    comentario. La migración 0047 lo conservó «como hoy» —sembró
    `ver_comentarios`/`ver_internos` sólo por rol primario— y la 0048 lo
    corrigió por decisión de Oscar (2026-09-28): quien tiene ASIGNADO un rol del
    sistema recibe las filas que ese rol le daría, y la 0049 lo volvió regla
    —los roles del sistema traen otra vez `ver_comentarios`/`ver_internos` en su
    JSON—, así que quien reciba el rol mañana lee igual. Para que alguien más
    los lea basta prender el permiso en El Directorio.
    """
    if es_super_admin(user):
        return True
    if not puede(user, "pizarron", "ver_comentarios"):
        return False
    if puede(user, "pizarron", "ver_internos"):
        return True
    if comentario.es_interno and comentario.autor_id != getattr(user, "pk", None):
        return False
    proyecto = comentario.proyecto or (comentario.tarea.proyecto if comentario.tarea else None)
    if proyecto is None:
        return False
    return puede_ver_proyecto(user, proyecto)


# ── La grilla por persona de El Directorio ───────────────────────────────────
#
# `puede()` resuelve un par `(modulo, accion)` así: si la persona tiene FILA
# propia, manda la fila (encendida o apagada); si no, lo que den sus roles
# asignados (`roles_extra`). El rol primario no entra: desde S-Roles-V2 se
# DERIVA de los asignados (super_admin sólo si tiene ese rol asignado), así que
# no aporta nada que los asignados no den ya.
#
# Hasta 2026-09-29 la grilla marcaba cada casilla por la fila o por los defaults
# del rol PRIMARIO, y al guardar escribía una fila por CADA acción del catálogo:
# un `miembro` con el rol Contador veía `contaduria.ver` desmarcado y «Guardar
# permisos» tal cual se lo apagaba (la fila apagada gana sobre el rol). Ahora la
# grilla enseña `efectivo_por_filas` —lo mismo que contesta `puede()`— y
# `plan_de_grilla` sólo deja filas donde la persona DIFIERE de sus roles.


def pares_de_roles(permisos_de_roles) -> set[tuple[str, str]]:
    """Los pares que dan unos roles, a partir de sus JSON `Rol.permisos`."""
    pares: set[tuple[str, str]] = set()
    for permisos_del_rol in permisos_de_roles:
        for modulo, acciones in (permisos_del_rol or {}).items():
            for accion in acciones or ():
                pares.add((modulo, accion))
    return pares


def efectivo_por_filas(filas: dict, por_rol: set, par: tuple[str, str]) -> bool:
    """La precedencia de `puede()` sin la parte de la sesión (usuario activo,
    «ver como rol»): la fila propia gana; sin fila, lo que den los roles.

    La grilla la usa en vez de `puede()` para que un usuario BLOQUEADO siga
    viendo sus casillas como son: con `puede()` saldrían todas apagadas y
    guardarlas le escribiría filas apagadas que le durarían al desbloquearlo."""
    if par in filas:
        return bool(filas[par])
    return par in por_rol


def plan_de_grilla(filas: dict, roles_antes: set, roles_despues: set,
                   elegidos: set, universo) -> tuple[dict, set]:
    """Qué filas escribir y cuáles borrar al guardar la grilla de una persona.

    - `filas`: `{(modulo, accion): activo}` que la persona tiene hoy.
    - `roles_antes` / `roles_despues`: pares que dan sus roles antes y después
      del guardado (el mismo POST puede asignar o quitar roles).
    - `elegidos`: pares que llegaron marcados.
    - `universo`: pares que la grilla enseña (el catálogo). Una fila fuera de
      él no se toca.

    Devuelve `(escribir, borrar)`: `escribir` es `{par: activo}` y `borrar` un
    set de pares.

    Por par, la casilla que la persona VIO es `efectivo_por_filas(filas,
    roles_antes)`. Si llegó distinta, quien guarda la cambió: eso es lo que
    queda. Si llegó igual, no opinó: se conserva lo puesto a mano (una fila que
    difiere de sus roles de antes) y lo demás sigue a sus roles de DESPUÉS
    —así asignar un rol en el mismo clic le da lo que el rol da, y quitárselo
    le quita lo que le daba—.

    Sólo se deja fila donde lo que queda difiere de `roles_despues`. Borrar la
    fila que coincide no cambia el permiso efectivo: sin fila, `puede()`
    contesta lo que dan los roles, que es justo lo que la fila decía. Con los
    roles sin cambiar, lo efectivo después es exactamente `elegidos`.
    """
    escribir: dict = {}
    borrar: set = set()
    for par in universo:
        fila = filas.get(par)
        del_rol_antes = par in roles_antes
        visto = fila if fila is not None else del_rol_antes
        elegido = par in elegidos
        if elegido != visto:
            queda = elegido
        elif fila is not None and fila != del_rol_antes:
            queda = fila
        else:
            queda = None  # sigue a sus roles
        if queda is None or queda == (par in roles_despues):
            if fila is not None:
                borrar.add(par)
        elif fila != queda:
            escribir[par] = queda
    return escribir, borrar


# ── Caché de permisos por instancia de usuario ───────────────────────────────
#
# `puede()` hacía DOS consultas por llamada (revocado + concedido) y el sistema
# la llama decenas de veces por petición: el context processor `permisos_modulos`
# recorre los ~23 módulos del catálogo, y encima las vistas y las plantillas
# vuelven a preguntar. Medido en producción (2026-08-24), el detalle de un
# proyecto gastaba 60 de sus 231 consultas en la tabla de permisos, y el banner
# de deploy —que sólo devuelve un div vacío y se pide cada 10 s— gastaba 46.
#
# El arreglo es leer TODOS los permisos del usuario de una vez y resolver en
# memoria. El resultado se memoiza en la propia instancia de `Usuario`, que vive
# lo que dura la petición: no es un caché compartido entre peticiones ni entre
# trabajadores, así que no puede servir permisos viejos a nadie más.
#
# La única ventana en la que el memo podría mentir es dentro de UNA petición que
# cambia permisos y vuelve a leerlos (el panel de El Directorio). Por eso los
# signals de `PermisoUsuario` y del M2M de roles suben `_VERSION_PERMISOS`, y el
# memo que se llenó con una versión anterior se descarta.

_VERSION_PERMISOS = 0
_ATRIBUTO_MEMO = "_despacho_memo_permisos"


def invalidar_cache_permisos(*args, **kwargs) -> None:
    """Descarta los memos vigentes. La llaman los signals de `PermisoUsuario`
    y de `Usuario.roles_extra`; también sirve desde un test o un command que
    mute permisos y quiera releerlos en el mismo proceso."""
    global _VERSION_PERMISOS
    _VERSION_PERMISOS += 1


def _cargar_permisos(usuario) -> dict:
    """Lee de la base todo lo que `puede()` necesita: DOS consultas.

    Devuelve `{"revocados": set, "concedidos": set, "por_rol": set}` con pares
    `(modulo, permiso)`. El orden de precedencia lo aplica `puede()`, no aquí.
    """
    revocados: set[tuple[str, str]] = set()
    concedidos: set[tuple[str, str]] = set()
    from cuentas.models.permiso_usuario import PermisoUsuario

    for modulo, permiso, activo in PermisoUsuario.objects.filter(
        usuario=usuario
    ).values_list("modulo", "permiso", "activo"):
        (concedidos if activo else revocados).add((modulo, permiso))

    por_rol = pares_de_roles(usuario.roles_extra.values_list("permisos", flat=True))

    return {"revocados": revocados, "concedidos": concedidos, "por_rol": por_rol}


def _permisos_de(usuario) -> dict:
    """El mapa de permisos del usuario, memoizado en su propia instancia."""
    memo = getattr(usuario, _ATRIBUTO_MEMO, None)
    if memo is not None and memo["version"] == _VERSION_PERMISOS:
        return memo["mapa"]
    mapa = _cargar_permisos(usuario)
    with contextlib.suppress(Exception):  # usuario sin __dict__ (raro, pero no truena)
        setattr(usuario, _ATRIBUTO_MEMO, {"version": _VERSION_PERMISOS, "mapa": mapa})
    return mapa


def _permisos_del_rol_simulado(clave: str) -> dict:
    """Permisos del rol que el super_admin está simulando ("ver como rol")."""
    from cuentas.models.rol import Rol

    rol = Rol.objects.filter(clave=clave).first()
    return (rol.permisos or {}) if rol else {}


def puede(usuario, modulo: str, permiso: str) -> bool:
    """Pre-S2b.1: consulta PermisoUsuario granular.

    Retorna True si la fila `(usuario, modulo, permiso)` existe y `activo=True`.
    Usuario inactivo siempre False. Si la tabla no existe aún o falla la
    consulta, retorna False defensivamente.

    S-LC-Feedback-V5 c7: además consulta `Usuario.roles_extra` — si
    cualquier rol extra del usuario contiene el permiso, retorna True.
    El PermisoUsuario individual con `activo=False` SIEMPRE gana (revoca
    incluso permisos heredados por roles).
    """
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return False
    if not getattr(usuario, "is_active", True):
        return False
    # S-Roles-V2: "ver como rol" — evalúa SOLO contra los permisos del rol
    # simulado (Rol.permisos JSON), ignorando el super_admin/permisos reales.
    sim = getattr(usuario, "_rol_simulado", None)
    if sim:
        try:
            permisos = _permisos_del_rol_simulado(sim)
            return permiso in (permisos.get(modulo) or [])
        except Exception:
            return False
    try:
        mapa = _permisos_de(usuario)
        par = (modulo, permiso)
        # Override individual (activo=False) revoca incluso permisos por rol extra.
        if par in mapa["revocados"]:
            return False
        # Activo individual → True directo.
        if par in mapa["concedidos"]:
            return True
        # Fallback: roles extra del usuario (M2M Rol.permisos JSON).
        return par in mapa["por_rol"]
    except Exception:
        return False


def requiere_permiso(modulo: str, accion: str) -> Callable:
    """S-LC-Feedback-V10 — decorador de vista gateado por permiso GRANULAR.

    Reemplazó a `@requires_role(...)` (borrado en S-Deuda-Permisos: ya nadie lo
    usaba y sólo invitaba a gatear por rol) para que el super_admin pueda DELEGAR el acceso desde
    `/directorio/<id>/permisos/`. El super_admin es failsafe duro: siempre pasa,
    aunque no exista la fila de permiso (evita lock-out del despacho). Para
    cualquier otro usuario, exige `puede(user, modulo, accion)`.

    Regla del proyecto (decisión Oscar): TODA feature/módulo/herramienta nueva
    se gatea por permiso granular con este decorador (o el helper `puede()` en
    plantillas), nunca por rol literal.
    """
    def wrap(view: Callable) -> Callable:
        @wraps(view)
        def inner(request: HttpRequest, *args, **kwargs):
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                login_url = getattr(request, "_login_url", "/sign-in")
                return redirect(login_url)
            if tiene_rol(user, "super_admin") or puede(user, modulo, accion):
                return view(request, *args, **kwargs)
            return HttpResponseForbidden("Sin permisos para esta acción.")
        return inner
    return wrap


# ── Los KPIs (S-KPIs-V2, 2026-09-29) ────────────────────────────────────────


def puede_configurar_kpis(user) -> bool:
    """La Gerencia → Ajustes → KPIs: catálogo, tableros por rol, metas y
    constructor. También decide a quién le llega el aviso de una meta del
    despacho en riesgo."""
    return es_super_admin(user) or puede(user, "kpis", "configurar")
