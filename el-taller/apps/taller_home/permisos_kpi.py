"""Quién ve cada KPI: el permiso del DATO que enseña (§4 #20).

Hasta 2026.09.05 el catálogo de La Sala de Juntas se filtraba por `roles_visible`
(tuplas con nombres de rol). Ahora cada KPI declara los permisos granulares que
hacen falta para verlo —todos, si son varios— y `puede_ver` los evalúa con el
failsafe de `super_admin`. Así un KPI se delega desde El Directorio igual que la
pantalla de la que sale su número, y quien no puede abrir esa pantalla tampoco
ve su resumen en el tablero.

Decisión de Oscar: «como hoy». Con los defaults de cada rol del sistema cada
constante abre EXACTAMENTE a los mismos roles que abría la tupla vieja; lo
prueba `tests/test_kpis_por_permiso.py` rol por rol. Donde el permiso más fiel
al dato abriría a otro rol, se eligió el que conserva la audiencia y el porqué
queda aquí anotado.
"""

from __future__ import annotations

# ── Lo de cada quien (antes: los cuatro roles del sistema) ───────────────────
VE_PROYECTOS = ("proyectos.ver",)          # sus proyectos (el diseñador, los suyos)
VE_TAREAS = ("pizarron.ver",)              # sus tareas y los mandados del Pizarrón
VE_BUZON_PROPIO = ("buzon.ver_propios",)
VE_RECADOS = ("recados.ver",)
CHECA = ("checador.checar",)               # su jornada, sus visitas

# ── Lo del despacho entero (antes: super_admin, dueño y contador) ────────────
VE_TODOS_PROYECTOS = ("proyectos.ver_todos",)
VE_CARTERA = ("cartera.ver",)
VE_DINERO = ("tesoreria.ver",)
VE_COTIZACIONES = ("cotizaciones.ver",)
VE_FACTURACION = ("facturacion.ver",)
VE_CONTADURIA = ("contaduria.ver",)
VE_COSTOS = ("catalogo.ver_precios",)

# ── Lo de quien dirige (antes: super_admin y dueño) ──────────────────────────
GESTIONA_PROYECTOS = ("proyectos.editar",)  # y las tareas del equipo
EDITA_CARTERA = ("cartera.editar",)
EDITA_CATALOGO = ("catalogo.editar",)      # productos y proveedores
VE_MANDADOS_EQUIPO = ("pizarron.ver_todos_mandados",)
# El dato del soporte es `buzon.ver_todos`, pero por default sólo lo trae el
# super_admin y el dueño veía estos números: `buzon.eliminar` (borrar de la
# bandeja de soporte) es la acción del módulo que tiene su misma audiencia.
ATIENDE_SOPORTE = ("buzon.eliminar",)
CONFIGURA_INTERFONO = ("interfono.configurar",)
VE_SITE = ("site.ver",)                    # El Site y el fierro del NUC
VE_CHALANES = ("chalanes.ver",)            # gasto y uso de la IA
VE_DIRECTORIO = ("directorio.ver",)        # accesos y cuentas del equipo
# El dato es `checador.ver_equipo`, que hasta 2026-10-05 traía también el
# contador; estos KPIs nunca los vio: se usa la acción de quien supervisa las
# jornadas, que es la de su audiencia.
SUPERVISA_JORNADAS = ("checador.aprobar_correcciones",)
# Los asientos descuadrados son una alarma del dueño: el contador ve TODA La
# Contaduría y aun así este KPI nunca le salió. Ninguna acción de La Contaduría
# la separa, así que se pide además entrar a La Gerencia.
VIGILA_CONTADURIA = ("contaduria.ver", "gerencia.acceder")

# ── Los de desempeño (2026-09-29, `kpis_desempeno.py`) ───────────────────────
# Aprobadas que ya se facturaron: el dato cruza las dos pantallas.
COTIZA_Y_FACTURA = ("cotizaciones.ver", "facturacion.ver")
VE_RUTAS = ("rutas.ver",)                  # el planeador de rutas de reparto
ENVIA_CAMPANAS = ("comunicacion.campanas",)
# Proyectos sin documentos: el archivo (Paperless) de TODOS los proyectos.
VE_PAPELEO_PROYECTOS = ("papeleo.ver", "proyectos.ver_todos")


def puede_ver(user, permisos: tuple[str, ...]) -> bool:
    """¿`user` tiene TODOS los `permisos` («modulo.accion»)? super_admin
    siempre (failsafe). Una tupla vacía es de todos (los KPIs del Chalán)."""
    from lib.permisos import es_super_admin, puede

    if not permisos:
        return True
    if es_super_admin(user):
        return True
    return all(puede(user, *p.split(".", 1)) for p in permisos)


def puede_ver_con(mapa: dict, permisos: tuple[str, ...]) -> bool:
    """Lo mismo contra un JSON de permisos `{modulo: [acciones]}` —los defaults
    de un rol— para las llamadas que sólo traen el nombre de un rol."""
    return all(
        accion in (mapa.get(modulo) or ())
        for modulo, accion in (p.split(".", 1) for p in permisos)
    )
