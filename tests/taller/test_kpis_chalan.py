"""El Chalán y MCP con los KPIs de S-KPIs-V2: metas, tablero, configuración y
«fijar meta» por chat. Toda capacidad nueva va con su módulo MCP (regla de
Oscar); aquí se prueba el contrato y su candado."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.django_db


def _accion(payload):
    return SimpleNamespace(payload=payload, entidad_tipo=None, entidad_id=None)


def _registro():
    import capacidades  # noqa: F401 — registra lecturas y propuestas
    from capacidades.registro import CAPACIDADES

    return CAPACIDADES


def _capacidad(nombre):
    return _registro()[nombre]


def test_las_capacidades_nuevas_estan_registradas():
    registro = _registro()
    for nombre in ("metas_kpi", "mi_tablero_kpis", "configuracion_kpi", "fijar_meta_kpi"):
        assert nombre in registro, nombre
    assert registro["fijar_meta_kpi"].modo == "propuesta"
    assert registro["configuracion_kpi"].gating == "kpis"


def test_configuracion_kpi_pide_permiso(usuario_factory):
    from capacidades.gating import gate_ok

    assert gate_ok("kpis", usuario_factory(rol="super_admin"))
    assert not gate_ok("kpis", usuario_factory(rol="disenador"))


def test_metas_kpi_ensena_solo_lo_que_toca(usuario_factory):
    from apps.taller_home.models import MetaKPI

    admin = usuario_factory(rol="super_admin")
    ana = usuario_factory(rol="disenador")
    beto = usuario_factory(rol="disenador")
    MetaKPI.objects.create(kpi_slug="ingresos-mes", valor=Decimal("250000"), periodo="mes")
    MetaKPI.objects.create(kpi_slug="checador-horas-semana", ambito="persona", usuario=ana,
                           valor=Decimal("40"), periodo="semana")
    MetaKPI.objects.create(kpi_slug="checador-horas-semana", ambito="persona", usuario=beto,
                           valor=Decimal("40"), periodo="semana")
    fn = _capacidad("metas_kpi").fn
    assert fn({}, admin)["cuantas"] == 3
    de_ana = fn({}, ana)
    # Ana no ve el dinero (sin tesoreria.ver) ni la meta de Beto.
    assert [m["para"] for m in de_ana["metas"]] == [ana.nombre_completo]
    assert fn({"slug": "ingresos-mes"}, admin)["metas"][0]["meta"] == "$250,000"


def test_mi_tablero_kpis(usuario_factory):
    from apps.taller_home.views import COMPACT_KPI_SLUGS

    r = _capacidad("mi_tablero_kpis").fn({}, usuario_factory(rol="super_admin"))
    assert [f["slug"] for f in r["tablero"]] == list(COMPACT_KPI_SLUGS)


def test_configuracion_kpi(usuario_factory):
    from apps.taller_home.models import ConfigKPI

    ConfigKPI.objects.create(kpi_slug="cxc-total", umbral_rojo=Decimal("100000"))
    r = _capacidad("configuracion_kpi").fn({"slug": "cxc-total"}, usuario_factory(rol="super_admin"))
    assert r["hacia_donde_es_mejor"] == "menos es mejor"
    assert r["umbral_rojo"] == 100000.0 and r["tableros_de_rol"] == ["por omisión"]


def test_la_serie_de_un_kpi_ajeno_no_se_entrega(usuario_factory):
    from apps.taller_home import series

    from capacidades.mcp_lecturas import serie_indicador_impl

    series.guardar("ingresos-mes", 1000)
    disenador = usuario_factory(rol="disenador")
    assert serie_indicador_impl({"slug": "ingresos-mes"}, disenador) == {"error": "no_visible"}
    assert "error" in _capacidad("serie_kpi").fn({"slug": "ingresos-mes"}, disenador)
    admin = usuario_factory(rol="super_admin")
    assert serie_indicador_impl({"slug": "ingresos-mes"}, admin)["slug"] == "ingresos-mes"


# ── fijar_meta_kpi ───────────────────────────────────────────────────────

def test_fijar_meta_del_despacho(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.taller_home.models import MetaKPI

    admin = usuario_factory(rol="super_admin")
    accion = _accion({"kpi_slug": "ingresos-mes", "valor": "250,000"})
    EJECUTORES["fijar_meta_kpi"](accion, admin, {})
    meta = MetaKPI.objects.get(pk=accion.entidad_id)
    assert (meta.valor, meta.periodo, meta.ambito) == (Decimal("250000"), "mes", "despacho")

    EJECUTORES["fijar_meta_kpi"](_accion({"kpi_slug": "ingresos-mes", "quitar": True}), admin, {})
    assert not MetaKPI.objects.exists()


def test_fijar_meta_de_persona(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.taller_home.models import MetaKPI

    admin = usuario_factory(rol="super_admin")
    ana = usuario_factory(rol="disenador", email="ana@x.com")
    EJECUTORES["fijar_meta_kpi"](_accion({"kpi_slug": "checador-horas-semana", "valor": 40,
                                          "ambito": "persona", "usuario_email": "ANA@x.com"}), admin, {})
    assert MetaKPI.objects.get().usuario == ana


@pytest.mark.parametrize("payload, texto", [
    ({"kpi_slug": "no-existe", "valor": 1}, "No encontré"),
    ({"kpi_slug": "mis-tareas-vencidas", "valor": 1}, "no admite"),
    ({"kpi_slug": "ingresos-mes", "valor": 0}, "mayor que cero"),
    ({"kpi_slug": "ingresos-mes", "quitar": True}, "no tenía meta"),
])
def test_fijar_meta_rechaza(usuario_factory, payload, texto):
    from apps.el_dictado.ejecutores import EJECUTORES

    with pytest.raises(Exception, match=texto):
        EJECUTORES["fijar_meta_kpi"](_accion(payload), usuario_factory(rol="super_admin"), {})


def test_fijar_meta_sin_permiso(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["fijar_meta_kpi"](_accion({"kpi_slug": "ingresos-mes", "valor": 1}),
                                     usuario_factory(rol="disenador"), {})
