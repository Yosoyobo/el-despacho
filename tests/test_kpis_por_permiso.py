"""Candado de S-Fin-KPIs: los KPIs, las sugerencias, el hero del Inicio, las
categorías de push y los destinatarios de avisos deciden por PERMISO (§4 #20)
— y con los defaults de cada rol nadie gana ni pierde nada.

Decisión de Oscar (2026-09-28): «como hoy».

La regla VIEJA de cada zona está copiada abajo, congelada tal como estaba en
`origin/main` (2026.09.05) antes del sprint. Se compara contra la NUEVA:

1. **Rol por rol**, para los usuarios de un solo rol del sistema (la forma en
   que los defaults se reparten): TODO igual, en todas las zonas.
2. **Cada combinación** de rol primario × roles asignados (160 usuarios). Las
   zonas que leían los roles EFECTIVOS (catálogo de KPIs, sugerencias,
   categorías, destinatarios) deben dar lo mismo; las que leían el rol PRIMARIO
   (hero, zona compacta, consultar un KPI desde El Chalán) deben dar lo mismo
   que su regla leída con los roles efectivos. Las únicas diferencias admitidas
   están enumeradas (`ADMITIDAS`) con su porqué: son imposibles de igualar sin
   inventar un permiso.
3. **La foto de producción** del 2026-09-28 (la de
   `tests/test_permisos_sin_rol_literal.py`, tras la 0047): se fija
   EXACTAMENTE qué cambia para cada persona real.

Si una comparación falla, alguien ganó o perdió algo: no se ajusta la prueba,
se entiende por qué.
"""

from __future__ import annotations

import itertools
from types import SimpleNamespace

import pytest

from lib import permisos
from lib.permisos import roles_efectivos

pytestmark = pytest.mark.django_db

# ═════════════════════════════════════════════════════════════════════════════
# La regla VIEJA, congelada
# ═════════════════════════════════════════════════════════════════════════════

_TODOS = frozenset({"super_admin", "dueno", "contador", "disenador"})
_FIN = frozenset({"super_admin", "dueno", "contador"})
_ADMIN = frozenset({"super_admin", "dueno"})

# `roles_visible` de cada KPI del catálogo (kpis.py + kpis_bi.py), tal cual.
_VIEJO_POR_AUDIENCIA = {
    _TODOS: [
        "proyectos-activos", "por-entregar-esta-semana", "proyectos-vencidos",
        "mis-tareas-vencidas", "mis-tareas-proximas-3d", "tareas-bloqueadas",
        "buzon-mios-sin-responder", "mis-recados-no-leidos", "recados-enviados-semana",
        "checador-horas-semana", "checador-retardos-mes", "checador-visitas-semana",
        "checador-horas-por-proyecto-top", "buzon-urgentes", "mandados-abiertos",
        "mandados-entregados-semana", "visitas-semana",
    ],
    _FIN: [
        "prospectos-pipeline", "valor-proyectos", "cotizados-sin-avance",
        "proyectos-en-pausa", "proyectos-sin-actividad", "clientes-activos",
        "clientes-nuevos-mes", "clientes-con-pry-activos", "ingresos-mes", "egresos-mes",
        "utilidad-mes", "cxc-total", "cxp-total", "reembolsos-pendientes",
        "cotizaciones-pendientes", "cotizaciones-vencidas", "cotizaciones-aprobadas-mes",
        "anticipos-pendientes", "facturas-pendientes-cobro", "facturas-vencidas",
        "monto-por-cobrar", "facturado-mes", "contaduria-asientos-mes",
        "contaduria-saldo-banco", "contaduria-utilidad-neta-mes",
        "conversion-oportunidades", "oportunidades-vivas", "cotizaciones-sin-enviar",
        "cotizaciones-enfriadas", "margen-real", "proyectos-en-perdida",
        "proyectos-bajo-margen", "dias-de-caja", "facturas-cfdi-sin-emitir",
        "productos-sin-costo", "margen-catalogo", "deuda-proveedores",
        "egresos-sin-proveedor", "ticket-promedio",
    ],
    _ADMIN: [
        "proyectos-cancelados-mes", "tareas-vencidas-equipo", "tareas-sin-asignar",
        "tareas-completadas-semana", "buzon-sin-responder", "buzon-bugs-abiertos",
        "buzon-sugerencias", "clientes-sin-proyectos", "interfon-suscripciones",
        "interfon-pushes-semana", "site-integraciones-rojo",
        "contaduria-balance-descuadrado", "buzon-tiempo-respuesta",
        "productos-usados-mes", "proveedores-activos", "clientes-dormidos",
        "concentracion-cliente", "mandados-sin-runner", "mandado-minutos-promedio",
        "mandado-km-mes", "nuc-cpu", "nuc-memoria", "nuc-disco", "nuc-contenedores",
        "ia-gasto-30d", "ia-llamadas-30d", "ia-fallos-pct", "accesos-hoy",
        "accesos-fallidos", "usuarios-activos-semana", "cuentas-sin-entrar",
        "horas-equipo-semana", "retardos-mes", "jornadas-sin-cerrar",
        "horas-imputadas-pct", "actividad-semana",
    ],
}
VIEJO = {slug: aud for aud, slugs in _VIEJO_POR_AUDIENCIA.items() for slug in slugs}

# Las sugerencias que además pedían `_es_admin` (super_admin/dueño efectivos).
_SUGERENCIAS_ADMIN = {"tareas-vencidas-equipo", "proyectos-sin-actividad", "buzon-sin-responder"}

# /perfil/notificaciones/: las categorías que se ofrecían por rol (efectivo).
_CATEGORIAS_VIEJAS = {"buzon": _ADMIN, "tesoreria_reembolso": _FIN, "cobranza": _FIN}

# Destinatarios: `usuarios_con_rol(...)` (primario + asignados, activos).
_DESTINOS_VIEJOS = {
    "Buzón (nuevo, estado, comentario)": _ADMIN,
    "proyecto nuevo": _ADMIN,
    "cobranza (factura vencida, anticipo)": _FIN,
    "reembolso pendiente": _FIN,
    "scout facturas vencidas": _FIN,
    "scout proyectos estancados": _ADMIN,
    "scout mandado sin runner que avance": _ADMIN,
    "resumen del día": _ADMIN,
    "recordatorio de tareas (admins)": _ADMIN,
    "presupuesto de IA rebasado": _ADMIN,
}


def _efectivos(u):
    return roles_efectivos(u)


def v_catalogo(u):
    """kpis_aplicables_a_rol(u.rol, user=u): primario ∪ efectivos."""
    roles = ({u.rol} if u.rol else set()) | _efectivos(u)
    return {s for s, aud in VIEJO.items() if roles & aud}


def v_zona_compacta(u, roles=None):
    """_compact_kpis: `rol not in kpi.roles_visible` con el rol PRIMARIO."""
    from apps.taller_home.views import COMPACT_KPI_SLUGS

    roles = {u.rol} if roles is None else roles
    return {s for s in COMPACT_KPI_SLUGS if roles & VIEJO[s]}


def v_hero_finanzas(u, roles=None):
    """_puede_finanzas(rol): rol PRIMARIO en super_admin/dueño/contador."""
    roles = {u.rol} if roles is None else roles
    return bool(roles & _FIN)


def v_hero_solo_suyo(u, roles=None):
    """`if rol == "disenador"`: el rol PRIMARIO. Leída con roles efectivos,
    es la condición «diseñador sin rol amplio» del resto del sistema."""
    if roles is None:
        return u.rol == "disenador"
    return "disenador" in roles and not (roles & _FIN)


def v_consultar_kpi(u, slug, roles=None):
    """capacidades.lecturas._h_consultar_kpi: el rol PRIMARIO."""
    roles = {u.rol} if roles is None else roles
    return bool(roles & VIEJO[slug])


def v_sugerencias(u):
    """Qué slugs de REGLAS podía sugerir (sin contar el conteo que dispara)."""
    roles = _efectivos(u) or {"disenador"}
    salida = set()
    for slug in ("tareas-vencidas-equipo", "proyectos-sin-actividad",
                 "buzon-sin-responder", "mis-tareas-vencidas"):
        if not (roles & VIEJO[slug]):
            continue
        if slug in _SUGERENCIAS_ADMIN and not (_efectivos(u) & _ADMIN):
            continue
        salida.add(slug)
    return salida


def v_categorias(u):
    roles = _efectivos(u)
    return {c for c, aud in _CATEGORIAS_VIEJAS.items() if roles & aud}


# ═════════════════════════════════════════════════════════════════════════════
# La regla NUEVA (las mismas preguntas, contestadas por el código de hoy)
# ═════════════════════════════════════════════════════════════════════════════

def n_catalogo(u):
    from apps.taller_home.kpis import kpis_aplicables

    return {k.slug for k in kpis_aplicables(u)} & set(VIEJO)


def n_zona_compacta(u):
    """La función real del Inicio (sin los KPIs del Chalán, que no traen)."""
    from apps.taller_home.views import COMPACT_KPI_SLUGS, _compact_kpis

    return {it["slug"] for it in _compact_kpis(u)} & set(COMPACT_KPI_SLUGS)


def n_hero_finanzas(u):
    from apps.taller_home.views import _puede_finanzas

    return _puede_finanzas(u)


def n_hero_solo_suyo(u):
    from apps.taller_home.views import _solo_lo_suyo

    return _solo_lo_suyo(u)


def n_consultar_kpi(u, slug):
    from capacidades.lecturas import _h_consultar_kpi

    return "error" not in _h_consultar_kpi({"slug": slug}, u)


def n_sugerencias(u):
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.permisos_kpi import puede_ver
    from apps.taller_home.sugerencias import REGLAS

    return {
        r["slug"] for r in REGLAS
        if kpi_por_slug(r["slug"]).visible_para(u) and puede_ver(u, r.get("permisos", ()))
    }


def n_categorias(u):
    from apps.perfil_notificaciones.views import _categorias_para

    return {s for s, _n, _d in _categorias_para(u)} & set(_CATEGORIAS_VIEJAS)


def _pks(usuarios):
    return {u.pk for u in usuarios}


def _presupuesto_ia(monkeypatch):
    """A quién le llega el aviso de presupuesto de IA rebasado (llamada real)."""
    import lib.interfono
    from cuentas.management.commands.evaluar_presupuestos_ia import Command

    llegaron = []
    monkeypatch.setattr(lib.interfono, "enviar_a_usuario", lambda u, **kw: llegaron.append(u.pk))
    p = SimpleNamespace(politica="alertar", usuario=SimpleNamespace(email="x@ejemplo.com"),
                        usuario_id=0, tope_usd=1)
    Command()._avisar_admins(p, 2)
    return set(llegaron)


def _recordatorio_admins():
    from apps.el_pizarron.management.commands.recordar_tareas_por_vencer import _destinatarios

    tarea = SimpleNamespace(asignada_a_id=None, proyecto_id=None)
    config = SimpleNamespace(incluir_asignado=False, incluir_lider=False, incluir_admins=True)
    return _pks(_destinatarios(tarea, config))


def n_destinos(monkeypatch):
    from apps.el_dictado import scouts
    from apps.taller_home import push_handlers as ph
    from apps.tesoreria import push_handlers as tph

    return {
        "Buzón (nuevo, estado, comentario)": _pks(ph._soporte_activos()),
        "proyecto nuevo": _pks(ph._gestores_activos()),
        "cobranza (factura vencida, anticipo)": _pks(ph._cobranza_activos()),
        "reembolso pendiente": _pks(tph._contadores_y_admins_activos()),
        "scout facturas vencidas": _pks(scouts._cobranza_users()),
        "scout proyectos estancados": _pks(scouts._gestores()),
        "scout mandado sin runner que avance": _pks(scouts._supervisores_de_mandados()),
        "resumen del día": _pks(scouts._destinatarios_digest()),
        "recordatorio de tareas (admins)": _recordatorio_admins(),
        "presupuesto de IA rebasado": _presupuesto_ia(monkeypatch),
    }


def v_destinos(usuarios):
    return {
        nombre: {u.pk for u in usuarios if _efectivos(u) & aud}
        for nombre, aud in _DESTINOS_VIEJOS.items()
    }


# ═════════════════════════════════════════════════════════════════════════════
# Los usuarios
# ═════════════════════════════════════════════════════════════════════════════

PRIMARIOS = ("super_admin", "dueno", "contador", "disenador", "miembro")
ASIGNABLES = ("super_admin", "dueno", "contador", "disenador", "runner")
SISTEMA = ("super_admin", "dueno", "contador", "disenador")


def _rol(clave):
    from cuentas.models.rol import Rol

    return Rol.objects.get(clave=clave)


@pytest.fixture
def todos(usuario_factory):
    """160 usuarios: 5 primarios × 32 combinaciones de roles asignados."""
    roles = {c: _rol(c) for c in ASIGNABLES}
    salida = []
    for primario in PRIMARIOS:
        for n in range(len(ASIGNABLES) + 1):
            for extra in itertools.combinations(ASIGNABLES, n):
                u = usuario_factory(rol=primario)
                if extra:
                    u.roles_extra.add(*(roles[c] for c in extra))
                salida.append((f"{primario}+{'+'.join(extra) or '∅'}", primario, extra, u))
    permisos.invalidar_cache_permisos()
    return salida


def _puro(primario, extra):
    """Un solo rol del sistema (o ninguno): primario X, asignado X o nada.
    `miembro` puro es «sin rol»; `miembro`+X es como hoy se da un rol."""
    if primario == "miembro":
        return len(extra) <= 1 and set(extra) <= set(SISTEMA)
    return set(extra) <= {primario}


# El rol «Runner» (opt-in, cuentas/0033) no es de los cuatro: la regla vieja no
# le daba NINGÚN KPI ni aviso, porque su clave no estaba en ninguna tupla. La
# nueva mira lo que su JSON sí trae (sus tareas, sus recados, su jornada…): ver
# SUS cosas no se puede negar sin inventar un permiso «ver tablero». Son estos
# KPIs, y SÓLO para quien no tenía ya un rol de los cuatro.
RUNNER_GANA_KPIS = {
    "mis-tareas-vencidas", "mis-tareas-proximas-3d", "tareas-bloqueadas",
    "buzon-mios-sin-responder", "buzon-urgentes", "mis-recados-no-leidos",
    "recados-enviados-semana", "checador-horas-semana", "checador-retardos-mes",
    "checador-visitas-semana", "checador-horas-por-proyecto-top", "visitas-semana",
    "mandados-abiertos", "mandados-entregados-semana",
}


class TestRolPorRol:
    """Con los defaults de cada rol, nadie gana ni pierde NADA."""

    def test_cada_zona_igual_para_cada_rol_del_sistema(self, todos, monkeypatch):
        distintas = []
        puros = [(e, u) for e, p, x, u in todos if _puro(p, x)]
        assert len(puros) == 4 * 2 + 1 + 4  # X, X+X; miembro; miembro+X
        for etiqueta, u in puros:
            for zona, vieja, nueva in (
                ("catálogo", v_catalogo(u), n_catalogo(u)),
                ("sugerencias", v_sugerencias(u), n_sugerencias(u)),
                ("categorías", v_categorias(u), n_categorias(u)),
            ):
                if vieja != nueva:
                    distintas.append(f"{etiqueta} · {zona}: gana {nueva - vieja}, pierde {vieja - nueva}")
        # Las zonas por rol PRIMARIO: el primario real de la gente con UN rol.
        for etiqueta, u in puros:
            if u.rol == "miembro" and etiqueta != "miembro+∅":
                continue  # miembro+X: ver TestCombinaciones (su primario no es su rol)
            for zona, vieja, nueva in (
                ("zona compacta", v_zona_compacta(u), n_zona_compacta(u)),
                ("hero: dinero", v_hero_finanzas(u), n_hero_finanzas(u)),
                ("hero: sólo lo suyo", v_hero_solo_suyo(u), n_hero_solo_suyo(u)),
                ("Chalán: consultar KPI",
                 {s for s in VIEJO if v_consultar_kpi(u, s)},
                 {s for s in VIEJO if n_consultar_kpi(u, s)}),
            ):
                if vieja != nueva:
                    distintas.append(f"{etiqueta} · {zona}: antes {vieja}, ahora {nueva}")
        assert not distintas, "Alguien ganó o perdió:\n" + "\n".join(distintas)

    def test_destinatarios_igual(self, usuario_factory, monkeypatch):
        """Una persona por rol del sistema (primario y asignado) + un miembro."""
        usuarios = []
        for clave in SISTEMA:
            usuarios.append(usuario_factory(rol=clave))
            m = usuario_factory(rol="miembro")
            m.roles_extra.add(_rol(clave))
            usuarios.append(m)
        usuarios.append(usuario_factory(rol="miembro"))
        permisos.invalidar_cache_permisos()
        viejos, nuevos = v_destinos(usuarios), n_destinos(monkeypatch)
        distintas = [f"{n}: antes {viejos[n]}, ahora {nuevos[n]}" for n in viejos if viejos[n] != nuevos[n]]
        assert not distintas, "\n".join(distintas)

    def test_kpis_aplicables_a_rol_con_solo_el_nombre_sigue_los_defaults(self):
        """La llamada vieja por nombre de rol (sin usuario) = los defaults."""
        from apps.taller_home.kpis import kpis_aplicables_a_rol

        for clave in (*SISTEMA, "miembro"):
            esperado = {s for s, aud in VIEJO.items() if clave in aud}
            # Sólo los KPIs que existían (como `n_catalogo`): los nuevos no
            # tienen regla vieja contra la cual compararse.
            nuevos = {k.slug for k in kpis_aplicables_a_rol(clave)} & set(VIEJO)
            assert nuevos == esperado, clave


# (etiqueta de combinación, zona) → por qué cambia. Todo lo demás debe ser igual.
ADMITIDAS = {
    "runner": "El rol «Runner» no es de los cuatro: antes no veía nada; ahora ve lo SUYO (RUNNER_GANA_KPIS).",
}


def _gana_por_runner(etiqueta, u, vieja, nueva):
    """La diferencia se explica sólo por el Runner: el usuario no tenía un rol
    de los cuatro y lo que gana está en RUNNER_GANA_KPIS."""
    _p, extra = etiqueta.split("+", 1)
    return ("runner" in extra.split("+") and not (_efectivos(u) & _TODOS)
            and vieja <= nueva and (nueva - vieja) <= RUNNER_GANA_KPIS)


@pytest.fixture
def kpis_baratos(monkeypatch):
    """Aquí sólo importa QUIÉN ve cada KPI, no su número: 160 usuarios × 92
    KPIs calculados de verdad tardan minutos. Mismos KPIs (y mismos
    permisos), con un cálculo que no consulta nada."""
    import dataclasses

    from apps.taller_home import kpis, views

    baratos = {k.slug: dataclasses.replace(k, calcular=lambda u: {"valor": 0}) for k in kpis.KPIS}
    monkeypatch.setattr(kpis, "kpi_por_slug", baratos.get)
    monkeypatch.setattr(views, "kpi_por_slug", baratos.get)


@pytest.mark.usefixtures("kpis_baratos")
class TestCombinaciones:
    def test_zonas_por_roles_efectivos(self, todos, monkeypatch):
        distintas = []
        for etiqueta, _p, _x, u in todos:
            vieja, nueva = v_catalogo(u), n_catalogo(u)
            if vieja != nueva and not _gana_por_runner(etiqueta, u, vieja, nueva):
                distintas.append(f"{etiqueta} · catálogo: gana {nueva - vieja}, pierde {vieja - nueva}")
            for zona, vieja, nueva in (
                ("sugerencias", v_sugerencias(u), n_sugerencias(u)),
                ("categorías", v_categorias(u), n_categorias(u)),
            ):
                if vieja != nueva:
                    distintas.append(f"{etiqueta} · {zona}: gana {nueva - vieja}, pierde {vieja - nueva}")
        assert not distintas, "\n".join(distintas)

    def test_zonas_por_rol_primario_ahora_leen_los_roles_efectivos(self, todos):
        """Hero, zona compacta y «consultar KPI» leían el rol PRIMARIO; ahora
        dan lo mismo que esa regla leída con los roles EFECTIVOS (lo que hacía
        el resto del Inicio). Es la única forma de igualar a quien tiene un rol
        asignado sobre `miembro` —así se dan los roles desde S-Roles-V2— sin
        inventar un permiso: el permiso de un rol no sabe si llegó por el
        primario o por la asignación."""
        distintas = []
        for etiqueta, _p, _x, u in todos:
            roles = _efectivos(u)
            for zona, vieja, nueva in (
                ("zona compacta", v_zona_compacta(u, roles), n_zona_compacta(u)),
                ("hero: dinero", v_hero_finanzas(u, roles), n_hero_finanzas(u)),
                ("hero: sólo lo suyo", v_hero_solo_suyo(u, roles), n_hero_solo_suyo(u)),
                ("Chalán: consultar KPI",
                 {s for s in VIEJO if v_consultar_kpi(u, s, roles)},
                 {s for s in VIEJO if n_consultar_kpi(u, s)}),
            ):
                if vieja == nueva:
                    continue
                if isinstance(vieja, set) and _gana_por_runner(etiqueta, u, vieja, nueva):
                    continue
                distintas.append(f"{etiqueta} · {zona}: antes {vieja}, ahora {nueva}")
        assert not distintas, "\n".join(distintas)

    def test_destinatarios_por_roles_efectivos(self, todos, monkeypatch):
        usuarios = [u for *_r, u in todos]
        viejos, nuevos = v_destinos(usuarios), n_destinos(monkeypatch)
        etiqueta = {u.pk: e for e, *_r, u in todos}
        distintas = []
        for nombre in viejos:
            for pk in viejos[nombre] ^ nuevos[nombre]:
                distintas.append(f"{etiqueta[pk]} · {nombre}: {'pierde' if pk in viejos[nombre] else 'gana'}")
        assert not distintas, "\n".join(distintas)

    @pytest.mark.parametrize("simulado", SISTEMA[1:])
    def test_ver_como_rol_muestra_lo_del_rol_simulado(self, usuario_factory, simulado):
        """«Ver como rol» evalúa el JSON del rol simulado. Antes el catálogo
        sumaba el rol PRIMARIO del super_admin a la simulación y le enseñaba
        todo; ahora enseña lo que vería ese rol, que es lo que la función
        promete."""
        sa = usuario_factory(rol="super_admin")
        sa._rol_simulado = simulado
        esperado = {s for s, aud in VIEJO.items() if simulado in aud}
        assert n_catalogo(sa) == esperado


# ═════════════════════════════════════════════════════════════════════════════
# 3. La foto de producción (tras la 0047)
# ═════════════════════════════════════════════════════════════════════════════

# Lo que cambia para cada persona real. Usuario 4 = «Director» (rol clave
# `dueno`) sobre primario `miembro`; usuario 5 = «Administrativo», rol propio.
# Los ids 1 y 3 (super_admin) no cambian en nada.
_SITE = {"site-integraciones-rojo", "nuc-cpu", "nuc-memoria", "nuc-disco", "nuc-contenedores"}
_DIRECTORIO = {"accesos-hoy", "accesos-fallidos", "usuarios-activos-semana", "cuentas-sin-entrar"}
_INTERFONO = {"interfon-suscripciones", "interfon-pushes-semana"}
FOTO_CATALOGO = {
    # El Director deja de ver los KPIs de pantallas que en producción tiene
    # APAGADAS a mano (site.ver, directorio.ver, interfono.configurar): hoy los
    # veía por el nombre de su rol y su enlace le daba 403.
    4: {"pierde": _SITE | _DIRECTORIO | _INTERFONO, "gana": set()},
    # El Administrativo no veía NINGÚN KPI (su rol no es de los cuatro). Ahora
    # ve los de lo que ya puede abrir: cotizaciones, facturación, contaduría,
    # catálogo (costos y edición), El Directorio y los suyos. No ve dinero de La
    # Tesorería, clientes ni proyectos porque en producción los tiene apagados.
    5: {"pierde": set(), "gana": {
        "mis-tareas-vencidas", "mis-tareas-proximas-3d", "tareas-bloqueadas",
        "buzon-mios-sin-responder", "buzon-urgentes", "mis-recados-no-leidos",
        "recados-enviados-semana", "checador-horas-semana", "checador-retardos-mes",
        "checador-visitas-semana", "checador-horas-por-proyecto-top", "visitas-semana",
        "mandados-abiertos", "mandados-entregados-semana",
        "cotizaciones-pendientes", "cotizaciones-vencidas", "cotizaciones-aprobadas-mes",
        "conversion-oportunidades", "oportunidades-vivas", "cotizaciones-sin-enviar",
        "cotizaciones-enfriadas", "anticipos-pendientes", "facturas-pendientes-cobro",
        "facturas-vencidas", "monto-por-cobrar", "facturado-mes",
        "facturas-cfdi-sin-emitir", "contaduria-asientos-mes", "contaduria-saldo-banco",
        "contaduria-utilidad-neta-mes", "productos-sin-costo", "margen-catalogo",
        "productos-usados-mes", "proveedores-activos", *_DIRECTORIO,
    }},
}


@pytest.fixture
def foto(proyecto_factory):
    from django.apps import apps as django_apps

    from cuentas.models.permiso_usuario import PermisoUsuario
    from cuentas.models.rol import Rol
    from cuentas.models.usuario import Usuario
    from tests.test_permisos_sin_rol_literal import (
        FOTO_ROLES,
        FOTO_USUARIOS,
        _filas_de_la_foto,
        _migracion,
    )

    Rol.objects.all().delete()
    for rid, (clave, nombre, p) in FOTO_ROLES.items():
        Rol.objects.create(pk=rid, clave=clave, nombre=nombre, permisos=p)
    for uid, d in FOTO_USUARIOS.items():
        u = Usuario(pk=uid, email=f"foto{uid}@ejemplo.com", nombre_completo=f"Foto {uid}", rol=d["rol"])
        u.set_unusable_password()
        u.save()
        u.roles_extra.set(Rol.objects.filter(pk__in=d["roles"]))
    PermisoUsuario.objects.all().delete()
    PermisoUsuario.objects.bulk_create([
        PermisoUsuario(usuario_id=uid, modulo=m, permiso=a, activo=activo)
        for (uid, m, a), activo in _filas_de_la_foto().items()
    ])
    _migracion().aplicar(django_apps, None)
    permisos.invalidar_cache_permisos()
    return list(Usuario.objects.filter(pk__in=FOTO_USUARIOS).order_by("pk"))


class TestLaFotoDeProduccion:
    def test_el_catalogo_cambia_exactamente_esto(self, foto):
        cambios = {}
        for u in foto:
            vieja, nueva = v_catalogo(u), n_catalogo(u)
            if vieja != nueva:
                cambios[u.pk] = {"pierde": vieja - nueva, "gana": nueva - vieja}
        assert cambios == FOTO_CATALOGO

    def test_el_inicio_cambia_exactamente_esto(self, foto):
        """El hero y la zona compacta leían el primario: el Director (primario
        `miembro`) no veía NI UNA tarjeta de dinero en su Inicio aunque ve La
        Tesorería. Ahora ve las mismas que un dueño; el Administrativo, sin
        `tesoreria.ver`, sólo gana «Cotizaciones pendientes»."""
        from apps.taller_home.views import COMPACT_KPI_SLUGS

        cambios = {}
        for u in foto:
            antes = (v_hero_finanzas(u), v_zona_compacta(u))
            ahora = (n_hero_finanzas(u), n_zona_compacta(u))
            if antes != ahora:
                cambios[u.pk] = ahora
        assert cambios == {
            4: (True, set(COMPACT_KPI_SLUGS)),
            5: (False, {"cotizaciones-pendientes"}),
        }

    def test_sugerencias_categorias_y_avisos_no_cambian(self, foto, monkeypatch):
        """Salvo lo que sigue del catálogo: el Administrativo ya ve «Mis tareas
        vencidas», así que se la puede sugerir."""
        for u in foto:
            extra = {"mis-tareas-vencidas"} if u.pk == 5 else set()
            assert v_sugerencias(u) | extra == n_sugerencias(u), u.pk
            assert v_categorias(u) == n_categorias(u), u.pk
        viejos, nuevos = v_destinos(foto), n_destinos(monkeypatch)
        assert viejos == nuevos
