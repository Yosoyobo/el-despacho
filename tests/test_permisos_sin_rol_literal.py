"""Candado de S-Deuda-Permisos: las puertas que decidían por ROL ahora deciden
por permiso granular (§4 #20) — y nadie ganó ni perdió acceso.

Decisión de Oscar (2026-09-28, literal): «Como hoy».

Tres candados:

1. **Equivalencia rol por rol.** Para cada rol primario × cada combinación de
   roles asignados, la decisión de la puerta VIEJA (copiada abajo, congelada tal
   como estaba en `lib/permisos.py` y en las vistas antes del sprint) tiene que
   ser igual a la NUEVA, con proyecto asignado y sin asignar. Incluye «ver como
   rol» para las puertas que miraban los roles efectivos.
2. **La foto de producción.** Los permisos de producción del 2026-09-28
   (anonimizados: sólo ids, claves y acciones) se cargan, se corre la migración
   0047 y se compara persona por persona. También fija QUÉ filas toca.
3. **Que no reaparezca un rol literal** en `lib/permisos.py` ni en las vistas,
   fuera del failsafe `super_admin` y de la deuda que queda anotada abajo.

Si una comparación falla, alguien ganó o perdió acceso: no se ajusta la prueba,
se entiende por qué.
"""

from __future__ import annotations

import ast
import importlib
import itertools
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from lib import permisos
from lib.permisos import roles_efectivos, tiene_rol

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parent.parent

# ═════════════════════════════════════════════════════════════════════════════
# La regla VIEJA, congelada (copia de origin/main antes de S-Deuda-Permisos).
# `roles_efectivos` no cambió, así que se reusa.
# ═════════════════════════════════════════════════════════════════════════════

_ADMIN = {"super_admin", "dueno"}
_FIN = {"super_admin", "dueno", "contador"}
_TODOS = {"super_admin", "dueno", "contador", "disenador"}


def v_es_admin(u):
    return bool(roles_efectivos(u) & _ADMIN)


def v_finanzas(u):
    return bool(roles_efectivos(u) & _FIN)


def v_ver_proyecto(u, proyecto):
    roles = roles_efectivos(u)
    if roles & _FIN:
        return True
    if "disenador" in roles:
        return proyecto.asignaciones.filter(usuario_id=u.pk).exists()
    return False


def v_ver_comentario(u, c):
    rol = getattr(u, "rol", None)  # ← el rol PRIMARIO, no los efectivos
    if rol in ("super_admin", "dueno", "contador"):
        return True
    if rol == "disenador":
        if c.es_interno and c.autor_id != getattr(u, "pk", None):
            return False
        proyecto = c.proyecto or (c.tarea.proyecto if c.tarea else None)
        if proyecto is None:
            return False
        return v_ver_proyecto(u, proyecto)
    return False


def v_comentar_interno(u):
    # el_pizarron/views.py: `if not es_admin(u) and u.rol != "contador": interno=False`
    return v_es_admin(u) or getattr(u, "rol", None) == "contador"


def v_solo_asignados(u):
    # kpis._es_solo_disenador, calendario, checador, perfil_chalanes
    roles = roles_efectivos(u)
    return "disenador" in roles and not (roles & _FIN)


def v_proyectos_visibles(u):
    # los_proyectos.views._proyectos_visibles y calendario._proyectos_visibles_qs
    roles = roles_efectivos(u)
    if roles & _FIN:
        return "todos"
    if "disenador" in roles:
        return "asignados"
    return "ninguno"


def v_sa_o_dueno(u):
    return tiene_rol(u, "super_admin", "dueno")


# (nombre, vieja, nueva) — puertas que no dependen del proyecto ni del comentario.
PUERTAS = [
    ("editar_proyecto (y crear, asignar, dictar)", v_es_admin,
     lambda u: permisos.puede_editar_proyecto(u, None)),
    ("gestionar_proyectos / actividad de todos", v_es_admin, permisos.puede_gestionar_proyectos),
    ("archivar_proyecto", v_es_admin, permisos.puede_archivar_proyecto),
    ("ver_cartera", v_finanzas, permisos.puede_ver_cartera),
    ("editar_cartera", v_es_admin, permisos.puede_editar_cartera),
    ("ver_finanzas (y La Tesorería)", v_finanzas, permisos.puede_ver_finanzas),
    ("ver todos los proyectos / Pizarrón ve todo / MCP amplio",
     lambda u: v_es_admin(u) or v_finanzas(u), permisos.puede_ver_todos_proyectos),
    ("ve al menos sus proyectos (runner-only = lo contrario)",
     lambda u: bool(roles_efectivos(u) & _TODOS), permisos.puede_ver_proyectos_asignados),
    ("solo_proyectos_asignados", v_solo_asignados, permisos.solo_proyectos_asignados),
    ("comentar_interno", v_comentar_interno, permisos.puede_comentar_interno),
    ("eliminar tarea ajena", v_es_admin, lambda u: permisos.puede_eliminar_tarea(u, None)),
    ("ver todos los mandados", v_es_admin, permisos.puede_ver_todos_mandados),
    ("eliminar del Buzón", v_es_admin, permisos.puede_eliminar_buzon),
    ("API de El Site", v_sa_o_dueno, permisos.puede_usar_api_site),
    ("tablero de La Gerencia / refrescar Novedades", v_sa_o_dueno, permisos.puede_acceder_gerencia),
    ("saldo de Chalanes en El Taller", v_sa_o_dueno, permisos.puede_consultar_saldo_chalanes),
]

PRIMARIOS = ("super_admin", "dueno", "contador", "disenador", "miembro")
ASIGNABLES = ("super_admin", "dueno", "contador", "disenador", "runner")


def _rol(clave):
    from cuentas.models.rol import Rol

    return Rol.objects.get(clave=clave)


@pytest.fixture
def escenario(usuario_factory, proyecto_factory):
    """160 usuarios (5 primarios × 32 combinaciones de roles asignados), cada
    uno asignado a `propio` y no a `ajeno`."""
    from apps.los_proyectos.models import ProyectoAsignacion

    propio = proyecto_factory(nombre="Asignado")
    ajeno = proyecto_factory(nombre="Ajeno")
    roles = {c: _rol(c) for c in ASIGNABLES}
    usuarios = []
    for primario in PRIMARIOS:
        for n in range(len(ASIGNABLES) + 1):
            for extra in itertools.combinations(ASIGNABLES, n):
                u = usuario_factory(rol=primario)
                if extra:
                    u.roles_extra.add(*(roles[c] for c in extra))
                ProyectoAsignacion.objects.create(proyecto=propio, usuario=u)
                usuarios.append((f"{primario}+{'+'.join(extra) or '∅'}", u))
    permisos.invalidar_cache_permisos()
    return SimpleNamespace(usuarios=usuarios, propio=propio, ajeno=ajeno)


def _comentarios(autor_ajeno_id, proyecto, u):
    """Las cuatro clases de comentario que distingue la regla."""
    return {
        "público": SimpleNamespace(es_interno=False, autor_id=autor_ajeno_id, proyecto=proyecto, tarea=None),
        "interno ajeno": SimpleNamespace(es_interno=True, autor_id=autor_ajeno_id, proyecto=proyecto, tarea=None),
        "interno propio": SimpleNamespace(es_interno=True, autor_id=u.pk, proyecto=proyecto, tarea=None),
    }


class TestComoHoy:
    def test_cada_puerta_decide_igual_para_cada_combinacion_de_roles(self, escenario):
        distintas = []
        for etiqueta, u in escenario.usuarios:
            for nombre, vieja, nueva in PUERTAS:
                if vieja(u) != nueva(u):
                    distintas.append(f"{etiqueta}: {nombre} (antes {vieja(u)}, ahora {nueva(u)})")
            for cual, p in (("asignado", escenario.propio), ("ajeno", escenario.ajeno)):
                if v_ver_proyecto(u, p) != permisos.puede_ver_proyecto(u, p):
                    distintas.append(f"{etiqueta}: ver proyecto {cual}")
        assert not distintas, "Alguien ganó o perdió acceso:\n" + "\n".join(distintas)

    def test_comentarios_igual_salvo_el_failsafe(self, escenario):
        """La regla vieja leía el rol PRIMARIO. Única diferencia admitida: quien
        tiene super_admin ASIGNADO sobre otro primario ahora lee todo (el
        failsafe gana). Ese estado no existe en la vida real —asignar
        super_admin desde El Directorio vuelve primario al super_admin
        (`sincronizar_rol_primario`)— pero la prueba lo recorre igual."""
        distintas = []
        for etiqueta, u in escenario.usuarios:
            for cual, p in (("asignado", escenario.propio), ("ajeno", escenario.ajeno)):
                for clase, c in _comentarios(escenario.ajeno.creado_por_id, p, u).items():
                    esperado = v_ver_comentario(u, c) or permisos.es_super_admin(u)
                    if esperado != permisos.puede_ver_comentario(u, c):
                        distintas.append(f"{etiqueta}: comentario {clase} en proyecto {cual}")
        assert not distintas, "\n".join(distintas)

    def test_la_unica_diferencia_de_comentarios_es_ese_failsafe(self, escenario):
        """Que la excepción de arriba no esconda nada: sólo cambia para quien
        tiene super_admin asignado y NO lo tiene de primario."""
        cambian = set()
        for etiqueta, u in escenario.usuarios:
            for p in (escenario.propio, escenario.ajeno):
                for c in _comentarios(escenario.ajeno.creado_por_id, p, u).values():
                    if v_ver_comentario(u, c) != permisos.puede_ver_comentario(u, c):
                        cambian.add(etiqueta)
        assert cambian
        for etiqueta in cambian:
            primario, extra = etiqueta.split("+", 1)
            assert "super_admin" in extra.split("+") and primario in ("disenador", "miembro"), etiqueta

    def test_las_pantallas_filtran_igual(self, escenario):
        """No sólo el helper: los querysets reales de cada pantalla."""
        from apps.calendario import services as calendario
        from apps.checador import views as checador
        from apps.los_proyectos import views as proyectos

        from capacidades import mcp_lecturas

        todos = {escenario.propio.pk, escenario.ajeno.pk}
        esperado_por_estado = {"todos": todos, "asignados": {escenario.propio.pk}, "ninguno": set()}
        distintas = []
        for etiqueta, u in escenario.usuarios:
            estado = v_proyectos_visibles(u)
            esperado = esperado_por_estado[estado]
            for nombre, qs in (
                ("Proyectos", proyectos._proyectos_visibles(u)),
                ("Calendario", calendario._proyectos_visibles_qs(u)),
            ):
                if set(qs.values_list("pk", flat=True)) & todos != esperado:
                    distintas.append(f"{etiqueta}: {nombre}")
            # El cronómetro del Checador sólo acota al «diseñador sin rol amplio»;
            # a los demás les ofrece todos (así era).
            esperado_timer = {escenario.propio.pk} if v_solo_asignados(u) else todos
            if set(checador._proyectos_para(u).values_list("pk", flat=True)) & todos != esperado_timer:
                distintas.append(f"{etiqueta}: cronómetro del Checador")
            # MCP: super_admin/dueño/contador todo, los demás sus asignados.
            esperado_mcp = todos if roles_efectivos(u) & _FIN else {escenario.propio.pk}
            if set(mcp_lecturas._proyectos_visibles(u).values_list("pk", flat=True)) & todos != esperado_mcp:
                distintas.append(f"{etiqueta}: MCP")
        assert not distintas, "\n".join(distintas)

    @pytest.mark.parametrize("simulado", ["dueno", "contador", "disenador", "runner"])
    def test_ver_como_rol_decide_igual(self, usuario_factory, proyecto_factory, simulado):
        """«Ver como rol» evalúa SÓLO el JSON del rol simulado (`puede()`); la
        regla vieja, sólo su nombre. La 0047 dejó el JSON de los roles del
        sistema diciendo lo mismo que el nombre.

        Fuera de esta comparación, a propósito: los comentarios. Su regla vieja
        leía el rol PRIMARIO real (el super_admin simulando seguía leyéndolo
        todo); la nueva, el rol simulado — que es lo que «ver como rol»
        promete."""
        from apps.los_proyectos.models import ProyectoAsignacion

        sa = usuario_factory(rol="super_admin")
        propio, ajeno = proyecto_factory(), proyecto_factory()
        ProyectoAsignacion.objects.create(proyecto=propio, usuario=sa)
        sa._rol_simulado = simulado
        distintas = [n for n, vieja, nueva in PUERTAS if vieja(sa) != nueva(sa)]
        distintas += [f"proyecto {c}" for c, p in (("asignado", propio), ("ajeno", ajeno))
                      if v_ver_proyecto(sa, p) != permisos.puede_ver_proyecto(sa, p)]
        assert not distintas, f"simulando {simulado}: {distintas}"

    def test_el_disenador_ya_no_trae_editar_proyectos(self):
        """Decisión de Oscar: traía `editar` «sólo donde asignado», pero la
        puerta era el rol y nunca editó nada. Sin él, el permiso no miente."""
        from lib.permisos_defaults import DEFAULTS_POR_ROL

        assert "editar" not in DEFAULTS_POR_ROL["disenador"]["proyectos"]
        assert "editar" not in (_rol("disenador").permisos.get("proyectos") or [])


# ═════════════════════════════════════════════════════════════════════════════
# 2. La foto de producción del 2026-09-28 (anonimizada)
# ═════════════════════════════════════════════════════════════════════════════
FOTO_ROLES = {
    1: ('super_admin', 'super_admin', {
        'analisis': ['ver'],
        'buzon': ['responder', 'ver_propios', 'ver_todos'],
        'cartera': ['archivar', 'crear', 'editar', 'ver'],
        'catalogo': ['archivar', 'crear', 'editar', 'editar_precios', 'gestionar_categorias', 'ver_nombres', 'ver_precios'],
        'contaduria': ['anular', 'capturar', 'reportes', 'ver'],
        'cotizaciones': ['anular', 'aprobar', 'crear', 'editar', 'enviar', 'rechazar', 'ver'],
        'dictado': ['actualizar_proyecto', 'crear_proyecto', 'crear_tarea', 'registrar_egreso', 'registrar_ingreso'],
        'facturacion': ['cancelar', 'cobrar', 'crear', 'editar', 'emitir', 'ver'],
        'gerencia': ['acceder'],
        'mcp': ['usar'],
        'papeleo': ['ligar', 'subir', 'ver'],
        'pizarron': ['completar', 'crear', 'editar', 'ver', 'ver_internos'],
        'proyectos': ['asignar', 'cambiar_estado', 'crear', 'editar', 'ver'],
        'recados': ['adjuntar_drive', 'crear', 'editar_propios', 'ver', 'ver_historial_todos'],
        'rutas': ['despachar', 'planear', 'ver'],
        'tesoreria': ['anular', 'capturar_egreso', 'capturar_ingreso', 'dictado_gasto', 'exportar', 'ocr', 'reportes', 'ver'],
    }),
    2: ('dueno', 'Director', {
        'ajustes': ['acceder'],
        'buzon': ['responder', 'ver_propios', 'ver_todos'],
        'cartera': ['archivar', 'crear', 'editar', 'ver'],
        'catalogo': ['archivar', 'crear', 'editar', 'editar_precios', 'ver_nombres', 'ver_precios'],
        'catalogos': ['centros_costo', 'estados', 'tipos'],
        'chalan': ['usar'],
        'chalanes': ['configurar', 'ver'],
        'checador': ['aprobar_correcciones', 'checar', 'configurar_horarios', 'exportar', 'ver_equipo'],
        'comunicacion': ['campanas', 'enviar_correo'],
        'contaduria': ['anular', 'capturar', 'reportes', 'ver'],
        'cotizaciones': ['anular', 'aprobar', 'crear', 'editar', 'enviar', 'rechazar', 'ver'],
        'dictado': ['actualizar_proyecto', 'crear_proyecto', 'crear_tarea', 'registrar_egreso', 'registrar_ingreso'],
        'directorio': ['gestionar', 'ia', 'panel', 'permisos', 'roles', 'ver'],
        'facturacion': ['cancelar', 'cobrar', 'crear', 'editar', 'emitir', 'ver'],
        'gerencia': ['acceder'],
        'interfono': ['configurar'],
        'pizarron': ['completar', 'crear', 'editar', 'ver', 'ver_internos'],
        'proyectos': ['asignar', 'cambiar_estado', 'crear', 'editar', 'ver'],
        'recados': ['adjuntar_drive', 'crear', 'editar_propios', 'ver', 'ver_historial_todos'],
        'site': ['ver'],
        'tesoreria': ['anular', 'capturar_egreso', 'capturar_ingreso', 'dictado_gasto', 'exportar', 'ocr', 'reportes', 'ver'],
    }),
    4: ('disenador', 'disenador', {
        'buzon': ['responder', 'ver_propios'],
        'catalogo': ['ver_nombres'],
        'dictado': ['actualizar_proyecto', 'crear_tarea'],
        'pizarron': ['completar', 'crear', 'editar', 'ver'],
        'proyectos': ['editar', 'ver'],
        'recados': ['adjuntar_drive', 'crear', 'editar_propios', 'ver'],
    }),
    5: ('runner', 'Runner', {
        'buzon': ['ver_propios'],
        'catalogo': ['ver_nombres', 'ver_precios'],
        'chalan': ['usar'],
        'checador': ['checar'],
        'dictado': ['actualizar_proyecto', 'crear_tarea', 'registrar_egreso'],
        'directorio': ['ver'],
        'pizarron': ['ver', 'ver_internos'],
        'recados': ['adjuntar_drive', 'crear', 'ver', 'ver_historial_todos'],
        'runner': ['recibir'],
        'rutas': ['ver'],
        'tesoreria': ['capturar_egreso', 'ocr'],
    }),
    6: ('administrador', 'Administrativo', {
        'buzon': ['responder', 'ver_propios'],
        'cartera': ['archivar', 'crear', 'editar', 'ver'],
        'catalogo': ['archivar', 'crear', 'editar', 'editar_precios', 'gestionar_categorias', 'ver_nombres', 'ver_precios'],
        'chalan': ['usar'],
        'checador': ['checar'],
        'comunicacion': ['enviar_correo'],
        'contaduria': ['anular', 'capturar', 'reportes', 'ver'],
        'cotizaciones': ['anular', 'aprobar', 'enviar', 'rechazar', 'ver'],
        'dictado': ['crear_tarea', 'registrar_egreso', 'registrar_ingreso'],
        'directorio': ['ver'],
        'facturacion': ['cancelar', 'cobrar', 'crear', 'editar', 'emitir', 'ver'],
        'pizarron': ['crear', 'editar', 'ver'],
        'recados': ['adjuntar_drive', 'crear', 'editar_propios', 'ver', 'ver_historial_todos'],
        'tesoreria': ['anular', 'capturar_egreso', 'capturar_ingreso', 'dictado_gasto', 'exportar', 'ocr', 'reportes', 'ver'],
    }),
}
FOTO_USUARIOS = {
    1: {
        "rol": 'super_admin',
        "roles": [1],
        "encendidos": [
            'ajustes.acceder', 'analisis.ver', 'buzon.responder', 'buzon.ver_propios',
            'buzon.ver_todos', 'cartera.archivar', 'cartera.crear', 'cartera.editar',
            'cartera.eliminar', 'cartera.ver', 'catalogo.archivar', 'catalogo.crear',
            'catalogo.editar', 'catalogo.editar_precios', 'catalogo.eliminar', 'catalogo.gestionar_categorias',
            'catalogo.ver_nombres', 'catalogo.ver_precios', 'catalogos.centros_costo', 'catalogos.estados',
            'catalogos.tipos', 'chalan.usar', 'chalanes.configurar', 'chalanes.ver',
            'checador.aprobar_correcciones', 'checador.checar', 'checador.configurar_horarios', 'checador.exportar',
            'checador.ver_equipo', 'comunicacion.campanas', 'comunicacion.enviar_correo', 'contaduria.anular',
            'contaduria.capturar', 'contaduria.reportes', 'contaduria.ver', 'cotizaciones.anular',
            'cotizaciones.aprobar', 'cotizaciones.crear', 'cotizaciones.editar', 'cotizaciones.eliminar',
            'cotizaciones.enviar', 'cotizaciones.rechazar', 'cotizaciones.ver', 'dictado.actualizar_proyecto',
            'dictado.crear_proyecto', 'dictado.crear_tarea', 'dictado.registrar_egreso', 'dictado.registrar_ingreso',
            'directorio.gestionar', 'directorio.ia', 'directorio.panel', 'directorio.permisos',
            'directorio.roles', 'directorio.ver', 'facturacion.cancelar', 'facturacion.cobrar',
            'facturacion.crear', 'facturacion.editar', 'facturacion.emitir', 'facturacion.ver',
            'gerencia.acceder', 'interfono.configurar', 'mcp.usar', 'papeleo.ligar',
            'papeleo.subir', 'papeleo.ver', 'pizarron.completar', 'pizarron.crear',
            'pizarron.editar', 'pizarron.ver', 'pizarron.ver_internos', 'proyectos.asignar',
            'proyectos.cambiar_estado', 'proyectos.crear', 'proyectos.editar', 'proyectos.ver',
            'recados.adjuntar_drive', 'recados.crear', 'recados.editar_propios', 'recados.ver',
            'recados.ver_historial_todos', 'runner.recibir', 'rutas.despachar', 'rutas.planear',
            'rutas.ver', 'site.limpiar', 'site.ver', 'tesoreria.anular',
            'tesoreria.capturar_egreso', 'tesoreria.capturar_ingreso', 'tesoreria.dictado_gasto', 'tesoreria.exportar',
            'tesoreria.ocr', 'tesoreria.reportes', 'tesoreria.ver',
        ],
        "apagados": [
        ],
    },
    3: {
        "rol": 'super_admin',
        "roles": [1, 2],
        "encendidos": [
            'ajustes.acceder', 'analisis.ver', 'buzon.responder', 'buzon.ver_propios',
            'buzon.ver_todos', 'cartera.archivar', 'cartera.crear', 'cartera.editar',
            'cartera.eliminar', 'cartera.ver', 'catalogo.archivar', 'catalogo.crear',
            'catalogo.editar', 'catalogo.editar_precios', 'catalogo.eliminar', 'catalogo.gestionar_categorias',
            'catalogo.ver_nombres', 'catalogo.ver_precios', 'catalogos.centros_costo', 'catalogos.estados',
            'catalogos.tipos', 'chalan.usar', 'chalanes.configurar', 'chalanes.ver',
            'checador.aprobar_correcciones', 'checador.checar', 'checador.configurar_horarios', 'checador.exportar',
            'checador.ver_equipo', 'comunicacion.campanas', 'comunicacion.enviar_correo', 'contaduria.anular',
            'contaduria.capturar', 'contaduria.reportes', 'contaduria.ver', 'cotizaciones.anular',
            'cotizaciones.aprobar', 'cotizaciones.crear', 'cotizaciones.editar', 'cotizaciones.eliminar',
            'cotizaciones.enviar', 'cotizaciones.rechazar', 'cotizaciones.ver', 'dictado.actualizar_proyecto',
            'dictado.crear_proyecto', 'dictado.crear_tarea', 'dictado.registrar_egreso', 'dictado.registrar_ingreso',
            'directorio.gestionar', 'directorio.ia', 'directorio.panel', 'directorio.permisos',
            'directorio.roles', 'directorio.ver', 'facturacion.cancelar', 'facturacion.cobrar',
            'facturacion.crear', 'facturacion.editar', 'facturacion.emitir', 'facturacion.ver',
            'gerencia.acceder', 'interfono.configurar', 'mcp.usar', 'papeleo.ligar',
            'papeleo.subir', 'papeleo.ver', 'pizarron.completar', 'pizarron.crear',
            'pizarron.editar', 'pizarron.ver', 'pizarron.ver_internos', 'proyectos.asignar',
            'proyectos.cambiar_estado', 'proyectos.crear', 'proyectos.editar', 'proyectos.ver',
            'recados.adjuntar_drive', 'recados.crear', 'recados.editar_propios', 'recados.ver',
            'recados.ver_historial_todos', 'runner.recibir', 'rutas.despachar', 'rutas.planear',
            'rutas.ver', 'site.limpiar', 'site.ver', 'tesoreria.anular',
            'tesoreria.capturar_egreso', 'tesoreria.capturar_ingreso', 'tesoreria.dictado_gasto', 'tesoreria.exportar',
            'tesoreria.ocr', 'tesoreria.reportes', 'tesoreria.ver',
        ],
        "apagados": [
        ],
    },
    4: {
        "rol": 'miembro',
        "roles": [2],
        "encendidos": [
            'buzon.responder', 'buzon.ver_propios', 'cartera.archivar', 'cartera.crear',
            'cartera.editar', 'cartera.ver', 'catalogo.archivar', 'catalogo.crear',
            'catalogo.editar', 'catalogo.editar_precios', 'catalogo.ver_nombres', 'catalogo.ver_precios',
            'chalan.usar', 'chalanes.ver', 'checador.aprobar_correcciones', 'checador.checar',
            'checador.configurar_horarios', 'checador.exportar', 'checador.ver_equipo', 'contaduria.anular',
            'contaduria.capturar', 'contaduria.reportes', 'contaduria.ver', 'cotizaciones.anular',
            'cotizaciones.aprobar', 'cotizaciones.crear', 'cotizaciones.editar', 'cotizaciones.enviar',
            'cotizaciones.rechazar', 'cotizaciones.ver', 'dictado.actualizar_proyecto', 'dictado.crear_proyecto',
            'dictado.crear_tarea', 'dictado.registrar_egreso', 'dictado.registrar_ingreso', 'facturacion.cancelar',
            'facturacion.cobrar', 'facturacion.crear', 'facturacion.editar', 'facturacion.emitir',
            'facturacion.ver', 'gerencia.acceder', 'pizarron.completar', 'pizarron.crear',
            'pizarron.editar', 'pizarron.ver', 'pizarron.ver_internos', 'proyectos.asignar',
            'proyectos.cambiar_estado', 'proyectos.crear', 'proyectos.editar', 'proyectos.ver',
            'recados.adjuntar_drive', 'recados.crear', 'recados.editar_propios', 'recados.ver',
            'recados.ver_historial_todos', 'runner.recibir', 'tesoreria.anular', 'tesoreria.capturar_egreso',
            'tesoreria.capturar_ingreso', 'tesoreria.dictado_gasto', 'tesoreria.exportar', 'tesoreria.ocr',
            'tesoreria.reportes', 'tesoreria.ver',
        ],
        "apagados": [
            'ajustes.acceder', 'buzon.ver_todos', 'cartera.eliminar', 'catalogo.eliminar',
            'catalogo.gestionar_categorias', 'catalogos.centros_costo', 'catalogos.estados', 'catalogos.tipos',
            'chalanes.configurar', 'comunicacion.campanas', 'comunicacion.enviar_correo', 'cotizaciones.eliminar',
            'directorio.gestionar', 'directorio.ia', 'directorio.panel', 'directorio.permisos',
            'directorio.roles', 'directorio.ver', 'interfono.configurar', 'mcp.usar',
            'site.ver',
        ],
    },
    5: {
        "rol": 'miembro',
        "roles": [6],
        "encendidos": [
            'buzon.responder', 'buzon.ver_propios', 'cartera.ver', 'catalogo.archivar',
            'catalogo.crear', 'catalogo.editar', 'catalogo.editar_precios', 'catalogo.gestionar_categorias',
            'catalogo.ver_nombres', 'catalogo.ver_precios', 'chalan.usar', 'checador.checar',
            'checador.exportar', 'checador.ver_equipo', 'contaduria.anular', 'contaduria.capturar',
            'contaduria.reportes', 'contaduria.ver', 'cotizaciones.anular', 'cotizaciones.aprobar',
            'cotizaciones.enviar', 'cotizaciones.rechazar', 'cotizaciones.ver', 'dictado.actualizar_proyecto',
            'dictado.crear_tarea', 'dictado.registrar_egreso', 'dictado.registrar_ingreso', 'directorio.ver',
            'facturacion.cancelar', 'facturacion.cobrar', 'facturacion.crear', 'facturacion.editar',
            'facturacion.emitir', 'facturacion.ver', 'pizarron.ver', 'proyectos.ver',
            'recados.adjuntar_drive', 'recados.crear', 'recados.editar_propios', 'recados.ver',
            'runner.recibir', 'tesoreria.dictado_gasto', 'tesoreria.ocr', 'tesoreria.reportes',
        ],
        "apagados": [
            'ajustes.acceder', 'cartera.archivar', 'cartera.crear', 'cartera.editar',
            'catalogos.centros_costo', 'catalogos.estados', 'catalogos.tipos', 'chalanes.configurar',
            'chalanes.ver', 'checador.aprobar_correcciones', 'checador.configurar_horarios', 'comunicacion.campanas',
            'comunicacion.enviar_correo', 'cotizaciones.crear', 'cotizaciones.editar', 'dictado.crear_proyecto',
            'directorio.gestionar', 'directorio.ia', 'directorio.panel', 'directorio.permisos',
            'directorio.roles', 'gerencia.acceder', 'interfono.configurar', 'pizarron.completar',
            'pizarron.crear', 'pizarron.editar', 'pizarron.ver_internos', 'proyectos.asignar',
            'proyectos.cambiar_estado', 'proyectos.crear', 'proyectos.editar', 'recados.ver_historial_todos',
            'site.ver', 'tesoreria.anular', 'tesoreria.capturar_egreso', 'tesoreria.capturar_ingreso',
            'tesoreria.exportar', 'tesoreria.ver',
        ],
    },
}

# Lo que la 0047 escribe en esa foto, fila por fila, con su porqué.
FILAS_ESPERADAS_APAGADAS = {
    # Rol «Administrativo» (no es de los cuatro): Clientes le daba 403 y su
    # lista de proyectos salía vacía. Sólo le quedaba el renglón del menú.
    (5, "cartera", "ver"),
    (5, "proyectos", "ver"),
    # Rol «Director» sobre primario `miembro`: no lee comentarios (regla por
    # rol primario) y `ver_internos` no lo leía nadie.
    (4, "pizarron", "ver_internos"),
}
# Altas: cada acción nueva a quien el rol ya se la daba.
_NUEVAS_ADMIN = [
    ("proyectos", "ver_todos"), ("proyectos", "archivar"),
    ("pizarron", "comentar_interno"), ("pizarron", "eliminar"),
    ("pizarron", "ver_todos_mandados"), ("buzon", "eliminar"), ("site", "api"),
]
FILAS_ESPERADAS_ENCENDIDAS = (
    {(uid, m, a) for uid in (1, 3, 4) for m, a in _NUEVAS_ADMIN}
    | {(1, "pizarron", "ver_comentarios"), (3, "pizarron", "ver_comentarios")}
)


# Y lo que cambia en el JSON de cada rol: {rol_id: {modulo: (agrega, quita)}}.
_AGREGA_ADMIN = {
    "proyectos": ({"archivar", "ver_todos"}, set()),
    "buzon": ({"eliminar"}, set()),
    "site": ({"api"}, set()),
    # `ver_internos` sale: la regla de comentarios era por rol PRIMARIO.
    "pizarron": ({"comentar_interno", "eliminar", "ver_todos_mandados"}, {"ver_internos"}),
}
JSON_ESPERADO = {
    1: _AGREGA_ADMIN,                                   # super_admin
    2: _AGREGA_ADMIN,                                   # «Director» (clave dueno)
    4: {"proyectos": (set(), {"editar"})},              # diseñador: nunca editó
    5: {"pizarron": (set(), {"ver_internos"})},         # «Runner»: acción sin efecto
    # 6 «Administrativo»: rol personalizado, no se toca.
}


def _filas_de_la_foto():
    filas = {}
    for uid, datos in FOTO_USUARIOS.items():
        for clave in datos["encendidos"]:
            filas[(uid, *clave.split("."))] = True
        for clave in datos["apagados"]:
            filas[(uid, *clave.split("."))] = False
    return filas


def _migracion():
    return importlib.import_module("cuentas.migrations.0047_permisos_sin_rol_literal")


class TestLaFotoDeProduccion:
    def test_el_plan_toca_exactamente_estas_filas(self):
        roles = [{"id": rid, "clave": clave, "permisos": p} for rid, (clave, _n, p) in FOTO_ROLES.items()]
        usuarios = [{"id": uid, "rol": d["rol"], "roles": d["roles"]} for uid, d in FOTO_USUARIOS.items()]
        _json, filas = _migracion().planear(usuarios, roles, _filas_de_la_foto())
        apagadas = {(u, m, a) for u, m, a, activo in filas if not activo}
        encendidas = {(u, m, a) for u, m, a, activo in filas if activo}
        assert apagadas == FILAS_ESPERADAS_APAGADAS
        assert encendidas == FILAS_ESPERADAS_ENCENDIDAS
        cambios = {}
        for rid, nuevo in _json.items():
            viejo = FOTO_ROLES[rid][2]
            cambios[rid] = {
                m: (set(nuevo.get(m, [])) - set(viejo.get(m, [])), set(viejo.get(m, [])) - set(nuevo.get(m, [])))
                for m in set(viejo) | set(nuevo)
                if set(viejo.get(m, [])) != set(nuevo.get(m, []))
            }
        assert cambios == JSON_ESPERADO

    def test_nadie_gana_ni_pierde_con_los_datos_de_produccion(self, proyecto_factory):
        from apps.los_proyectos.models import ProyectoAsignacion
        from django.apps import apps as django_apps

        from cuentas.models.permiso_usuario import PermisoUsuario
        from cuentas.models.rol import Rol
        from cuentas.models.usuario import Usuario

        # Los roles y usuarios tal cual la foto (los ids son los de la foto).
        Rol.objects.all().delete()
        for rid, (clave, nombre, p) in FOTO_ROLES.items():
            Rol.objects.create(pk=rid, clave=clave, nombre=nombre, permisos=p)
        for uid, d in FOTO_USUARIOS.items():
            u = Usuario(pk=uid, email=f"foto{uid}@ejemplo.com", nombre_completo=f"Foto {uid}", rol=d["rol"])
            u.set_unusable_password()
            u.save()
            u.roles_extra.set(Rol.objects.filter(pk__in=d["roles"]))
        PermisoUsuario.objects.all().delete()  # las que sembró el signal
        PermisoUsuario.objects.bulk_create([
            PermisoUsuario(usuario_id=uid, modulo=m, permiso=a, activo=activo)
            for (uid, m, a), activo in _filas_de_la_foto().items()
        ])
        propio, ajeno = proyecto_factory(), proyecto_factory()
        for uid in FOTO_USUARIOS:
            ProyectoAsignacion.objects.create(proyecto=propio, usuario_id=uid)

        _migracion().aplicar(django_apps, None)
        permisos.invalidar_cache_permisos()
        distintas = []
        for u in Usuario.objects.filter(pk__in=FOTO_USUARIOS):
            for nombre, vieja, nueva in PUERTAS:
                if vieja(u) != nueva(u):
                    distintas.append(f"usuario {u.pk}: {nombre}")
            for cual, p in (("asignado", propio), ("ajeno", ajeno)):
                if v_ver_proyecto(u, p) != permisos.puede_ver_proyecto(u, p):
                    distintas.append(f"usuario {u.pk}: proyecto {cual}")
                for clase, c in _comentarios(ajeno.creado_por_id, p, u).items():
                    if v_ver_comentario(u, c) != permisos.puede_ver_comentario(u, c):
                        distintas.append(f"usuario {u.pk}: comentario {clase} {cual}")
        assert not distintas, "Con los datos de producción alguien cambia:\n" + "\n".join(distintas)

    def test_la_migracion_es_idempotente(self):
        roles = [{"id": rid, "clave": clave, "permisos": p} for rid, (clave, _n, p) in FOTO_ROLES.items()]
        usuarios = [{"id": uid, "rol": d["rol"], "roles": d["roles"]} for uid, d in FOTO_USUARIOS.items()]
        mig = _migracion()
        json1, filas1 = mig.planear(usuarios, roles, _filas_de_la_foto())
        roles2 = [{**r, "permisos": json1.get(r["id"], r["permisos"])} for r in roles]
        filas = _filas_de_la_foto()
        filas.update({(u, m, a): activo for u, m, a, activo in filas1})
        json2, filas2 = mig.planear(usuarios, roles2, filas)
        assert json2 == {} and filas2 == []


# ═════════════════════════════════════════════════════════════════════════════
# 3. Que no reaparezca un rol literal
# ═════════════════════════════════════════════════════════════════════════════

# Claves de rol que no pueden decidir una puerta. `super_admin` es el failsafe;
# `runner` no se busca aquí porque también es el nombre de un MÓDULO (`runner.recibir`);
# `miembro` es el primario neutro (no da nada).
ROLES_PROHIBIDOS = {"dueno", "contador", "disenador"}

# Deuda anotada: lugares que TODAVÍA nombran un rol. No son puertas de este
# sprint —o su versión granular cambiaría a alguien de hoy— y cada uno dice por
# qué, y CUÁNTOS literales tiene: un literal más (o un archivo nuevo) hace fallar
# la prueba; uno menos también — hay que bajar la cuenta o sacarlo de aquí.
DEUDA = {
    # La Sala de Juntas: el catálogo de 28 KPIs se filtra por `roles_visible`
    # (tuplas de rol). Pasarlo a permiso es decidir KPI por KPI qué lo abre.
    "el-taller/apps/taller_home/kpis.py": (8, "catálogo de KPIs por roles_visible"),
    "el-taller/apps/taller_home/sugerencias.py": (2, "reglas de sugerencias de KPIs"),
    # Tarjetas hero del Inicio: acotan por rol PRIMARIO `disenador`.
    "el-taller/apps/taller_home/views.py": (4, "hero del Inicio y KPIs compactos (rol primario)"),
    # A quién le llegan avisos (no es una puerta): usuarios_con_rol(...).
    "el-taller/apps/taller_home/push_handlers.py": (3, "destinatarios de push"),
    "el-taller/apps/tesoreria/push_handlers.py": (2, "destinatarios de push"),
    "el-taller/apps/el_dictado/scouts.py": (3, "destinatarios de los scouts"),
    "el-taller/apps/el_pizarron/management/commands/recordar_tareas_por_vencer.py": (1, "destinatarios"),
    "el-taller/apps/perfil_notificaciones/views.py": (5, "categorías de push por rol"),
    # La Gerencia: cuántos «admins» hay (conteo) y etiquetas de rol (texto).
    "la-gerencia/apps/el_directorio/views.py": (4, "conteo de admins en el tablero"),
    "la-gerencia/apps/gerencia_home/views.py": (3, "etiquetas legibles de los roles"),
    # Falsos positivos: la palabra no es un rol del sistema.
    # · el rol del usuario en un PROYECTO (líder/diseñador/…);
    "el-taller/apps/los_proyectos/models/asignacion.py": (2, "rol_en_proyecto"),
    "el-taller/apps/el_dictado/ejecutores/basicos.py": (3, "rol_en_proyecto"),
    "el-taller/apps/los_proyectos/views.py": (1, "rol_en_proyecto"),
    "el-taller/apps/los_proyectos/services_undo.py": (1, "rol_en_proyecto"),
    # · el dueño (runner) de una parada de ruta, clave de un dict.
    "el-taller/apps/el_pizarron/views.py": (1, "dueño de una parada (no es rol)"),
    # Texto del prompt: el nombre del rol del usuario, sin decidir nada.
    "el-taller/apps/el_dictado/prompt.py": (2, "texto del prompt"),
    "el-taller/apps/el_dictado/prompt_chat.py": (2, "texto del prompt"),
}

# Puertas por rol PRIMARIO que quedaron sin convertir: su versión granular SÍ
# cambiaría a alguien de hoy, así que las decide Oscar (ver el reporte).
DEUDA_PUERTAS_PRIMARIO = {
    "lib/middleware.py": (2, "La Gerencia echa al Taller a primario contador/diseñador"),
    "auth_google/views.py": (1, "SSO a La Gerencia sólo para primario super_admin/dueño"),
    "referencias/views.py": (3, "autocompletar @# acota al primario diseñador"),
}

CARPETAS_VISTAS = ("el-taller/apps", "la-gerencia/apps", "la-recepcion/apps",
                   "capacidades", "mcp_despacho", "campanas", "papeleo", "referencias",
                   "auth_google", "buzon", "interfono", "chalanes")


def _literales_de_rol(ruta: Path) -> list[tuple[int, str]]:
    """Constantes de texto que son EXACTAMENTE una clave de rol prohibida
    (un docstring nunca lo es)."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    return [(n.lineno, n.value) for n in ast.walk(arbol)
            if isinstance(n, ast.Constant) and n.value in ROLES_PROHIBIDOS]


def _archivos_py():
    for carpeta in CARPETAS_VISTAS:
        for ruta in sorted((RAIZ / carpeta).rglob("*.py")):
            rel = ruta.relative_to(RAIZ).as_posix()
            if "/migrations/" in rel or "/tests/" in rel:
                continue
            yield rel, ruta
    yield "lib/middleware.py", RAIZ / "lib/middleware.py"


class TestSinRolLiteral:
    def test_lib_permisos_no_nombra_mas_rol_que_el_failsafe(self):
        """En `lib/permisos.py` ninguna constante es un nombre de rol salvo
        `super_admin` (failsafe) y `miembro` (el primario neutro)."""
        ruta = RAIZ / "lib/permisos.py"
        assert _literales_de_rol(ruta) == []
        # Y no vuelven los helpers por rol.
        fuente = ruta.read_text(encoding="utf-8")
        for prohibido in ("def es_admin", "def requires_role", "def requires_any_role"):
            assert prohibido not in fuente

    def test_las_vistas_no_nombran_roles_fuera_de_la_deuda_anotada(self):
        encontrados = {}
        for rel, ruta in _archivos_py():
            literales = _literales_de_rol(ruta)
            if literales:
                encontrados[rel] = literales
        anotados = {**DEUDA, **DEUDA_PUERTAS_PRIMARIO}
        distintos = {
            r: v for r, v in encontrados.items()
            if len(v) != anotados.get(r, (0, ""))[0]
        }
        assert not distintos, (
            "Rol literal nuevo (§4 #20: gatea con @requiere_permiso / puede()):\n"
            + "\n".join(f"{r}:{ln} {lit!r}" for r, v in distintos.items() for ln, lit in v)
        )
        saldados = set(anotados) - set(encontrados)
        assert not saldados, f"Ya no nombran roles; sácalos de la deuda: {sorted(saldados)}"

    def test_ninguna_vista_pregunta_por_un_rol_que_no_sea_super_admin(self):
        """`tiene_rol(x, …)` / `usuarios_con_rol(…)` sólo con "super_admin", y
        `roles_efectivos(` fuera de la deuda. `es_admin` ya no existe."""
        patron = re.compile(r"\b(tiene_rol|usuarios_con_rol)\(([^)]*)\)")
        malos = []
        for rel, ruta in _archivos_py():
            if rel in DEUDA or rel in DEUDA_PUERTAS_PRIMARIO:
                continue
            texto = ruta.read_text(encoding="utf-8")
            for m in patron.finditer(texto):
                args = set(re.findall(r"[\"']([a-z_]+)[\"']", m.group(2)))
                if args - {"super_admin"}:
                    malos.append(f"{rel}: {m.group(0)}")
            if re.search(r"\broles_efectivos\(", texto) and rel != "mcp_despacho/herramientas.py":
                # mcp_despacho sólo lo REPORTA (identidad de la conexión).
                malos.append(f"{rel}: roles_efectivos(")
            if re.search(r"\bes_admin\(", texto):
                malos.append(f"{rel}: es_admin(")
        assert not malos, "\n".join(malos)

    def test_las_plantillas_no_gatean_por_rol(self):
        """Ni `user.rol == 'dueno'` ni `|tiene_rol:"contador"` en las plantillas."""
        patron = re.compile(
            r"""(\.rol\s*(==|!=|in)\s*['"](dueno|contador|disenador|runner)['"])"""
            r"""|(tiene_rol:["'][^"']*(dueno|contador|disenador|runner))"""
        )
        malos = []
        for carpeta in ("el-taller/templates", "la-gerencia/templates", "la-recepcion/templates"):
            for ruta in sorted((RAIZ / carpeta).rglob("*.html")):
                for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
                    if patron.search(linea):
                        malos.append(f"{ruta.relative_to(RAIZ)}:{n}")
        assert not malos, "\n".join(malos)
