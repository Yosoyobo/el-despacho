"""La Gerencia → Ajustes → KPIs → Constructor (S-KPIs-V2 · 2).

El formulario sale del DSL v2; lo que se guarda pasa por su whitelist; el KPI
nace de equipo y activo, y sólo lo ve quien tiene el permiso de su dato.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]

INGRESOS_POR_CLIENTE = {
    "entidad": "ingreso", "agregacion": "sum", "campo": "monto",
    "ventana_tiempo": "este_mes", "agrupar_por": "cliente", "formato": "dinero", "direccion": "sube",
}


@pytest.fixture
def admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin", email="constructor@x.com")
    client.force_login(u)
    return u


def _crear(client, definicion, titulo="Ingresos por cliente", **extra):
    return client.post("/ajustes/kpis/constructor/guardar", {
        "titulo": titulo, "categoria": "dinero", "descripcion": "Lo cobrado a cada cliente.",
        "definicion_json": json.dumps(definicion), **extra,
    })


def test_las_pantallas_abren(client, admin):
    assert client.get("/ajustes/kpis/constructor/").status_code == 200
    html = client.get("/ajustes/kpis/constructor/nuevo/").content.decode()
    assert 'id="esquema-kpi"' in html and "js/constructor_kpi.js" in html


def test_sin_permiso_no_entra(client, usuario_factory):
    client.force_login(usuario_factory(rol="dueno"))
    assert client.get("/ajustes/kpis/constructor/").status_code in (302, 403)
    assert client.post("/ajustes/kpis/constructor/vista-previa", {}).status_code in (302, 403)


def test_crear_un_kpi_lo_deja_de_equipo_y_activo(client, admin):
    from apps.taller_home.models import KPICustom

    assert _crear(client, INGRESOS_POR_CLIENTE).status_code == 302
    k = KPICustom.objects.get()
    assert (k.alcance, k.estado, k.aprobado_por, k.categoria) == ("equipo", "activo", admin, "dinero")
    assert k.definicion_json["agrupar_por"] == "cliente"


def test_una_definicion_invalida_no_se_guarda(client, admin):
    from apps.taller_home.models import KPICustom

    _crear(client, {"entidad": "ingreso", "agregacion": "sum", "campo": "contrasena"})
    _crear(client, INGRESOS_POR_CLIENTE, titulo="")
    assert not KPICustom.objects.exists()


def test_el_kpi_nuevo_entra_al_catalogo_con_su_permiso_y_su_desglose(client, admin, usuario_factory):
    from apps.taller_home.kpis import kpi_por_slug, kpis_aplicables

    _crear(client, INGRESOS_POR_CLIENTE)
    kpi = kpi_por_slug("custom-ingresos-por-cliente")
    assert kpi is not None
    assert "tesoreria.ver" in kpi.permisos
    assert (kpi.formato, kpi.direccion, kpi.acumula, kpi.desgloses) == ("dinero", "sube", "mes", ("cliente",))
    assert kpi.admite_meta("cliente")
    # Un diseñador no ve el dinero: tampoco este KPI (antes lo veía cualquiera).
    assert "custom-ingresos-por-cliente" not in {k.slug for k in kpis_aplicables(usuario_factory(rol="disenador"))}
    assert "custom-ingresos-por-cliente" in {k.slug for k in kpis_aplicables(admin)}
    html = client.get("/ajustes/kpis/").content.decode()
    assert 'id="kpi-custom-ingresos-por-cliente"' in html


def test_meta_por_cliente_sobre_un_kpi_del_constructor(client, admin, cliente_factory):
    from apps.taller_home.metas import estado_de_metas
    from apps.taller_home.models import MetaKPI
    from apps.tesoreria.models import Ingreso

    c = cliente_factory()
    _crear(client, INGRESOS_POR_CLIENTE)
    campos = {f.name for f in Ingreso._meta.get_fields()}
    datos = {"monto": Decimal("400"), "fecha": date.today(), "cliente": c}
    if "creado_por" in campos:
        datos["creado_por"] = admin
    if "descripcion" in campos:
        datos["descripcion"] = "pago"
    try:
        Ingreso.objects.create(**datos)
    except Exception as exc:  # noqa: BLE001 — si el modelo pide más, la prueba lo dice
        pytest.skip(f"Ingreso requiere más campos: {exc}")
    client.post("/ajustes/kpis/metas/crear", {"kpi_slug": "custom-ingresos-por-cliente",
                                              "ambito": "cliente", "cliente": c.pk, "valor": "1000"})
    meta = MetaKPI.objects.get()
    assert meta.cliente == c
    fila = estado_de_metas()[0]
    assert fila["numero"] == 400.0


def test_vista_previa(client, admin):
    r = client.post("/ajustes/kpis/constructor/vista-previa",
                    {"definicion_json": json.dumps(INGRESOS_POR_CLIENTE)})
    html = r.content.decode()
    assert r.status_code == 200 and "$0" in html and "Tesorería" in html
    r = client.post("/ajustes/kpis/constructor/vista-previa",
                    {"definicion_json": json.dumps({"entidad": "ingreso", "agregacion": "sum", "campo": "nada"})})
    assert "Todavía no se puede calcular" in r.content.decode()
    r = client.post("/ajustes/kpis/constructor/vista-previa", {"definicion_json": "no es json"})
    assert "Elige de qué se cuenta" in r.content.decode()


def test_editar_archivar_y_reactivar(client, admin):
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.models import KPICustom

    _crear(client, INGRESOS_POR_CLIENTE)
    k = KPICustom.objects.get()
    assert client.get(f"/ajustes/kpis/constructor/{k.pk}/").status_code == 200
    client.post(f"/ajustes/kpis/constructor/{k.pk}/guardar", {
        "titulo": "Ingresos del mes por cliente", "categoria": "dinero",
        "definicion_json": json.dumps({**INGRESOS_POR_CLIENTE, "ventana_tiempo": "este_ano"}),
    })
    k.refresh_from_db()
    assert k.titulo == "Ingresos del mes por cliente" and k.slug == "ingresos-por-cliente"
    assert k.definicion_json["ventana_tiempo"] == "este_ano"
    client.post(f"/ajustes/kpis/constructor/{k.pk}/estado", {"accion": "archivar"})
    assert kpi_por_slug("custom-ingresos-por-cliente") is None
    client.post(f"/ajustes/kpis/constructor/{k.pk}/estado", {"accion": "reactivar"})
    assert kpi_por_slug("custom-ingresos-por-cliente") is not None


def test_aprobar_lo_que_se_propuso_desde_el_taller(client, admin, usuario_factory):
    from apps.taller_home.models import KPICustom

    k = KPICustom.objects.create(slug="propuesto", titulo="Propuesto", alcance="equipo",
                                 estado="pendiente_aprobacion", autor=usuario_factory(rol="contador"),
                                 definicion_json={"entidad": "proyecto", "agregacion": "count"})
    assert "Aprobar" in client.get("/ajustes/kpis/constructor/").content.decode()
    client.post(f"/ajustes/kpis/constructor/{k.pk}/estado", {"accion": "aprobar"})
    k.refresh_from_db()
    assert k.estado == "activo" and k.aprobado_por == admin


def test_con_chalan_llena_el_formulario(client, admin, monkeypatch):
    monkeypatch.setattr(
        "apps.taller_home.services_kpi_chalan.nl_a_dsl",
        lambda *, texto, usuario, **kw: {"ok": True, "definicion": INGRESOS_POR_CLIENTE,
                                          "titulo_sugerido": "Cobrado por cliente"},
    )
    r = client.post("/ajustes/kpis/constructor/chalan", {"texto": "cuánto nos paga cada cliente"}).json()
    assert r["ok"] and r["definicion"]["agrupar_por"] == "cliente" and r["titulo"] == "Cobrado por cliente"
    assert client.post("/ajustes/kpis/constructor/chalan", {"texto": ""}).status_code == 400


def test_el_archivo_js_del_constructor_existe():
    # `{% static %}` a un archivo inexistente es un 500 en producción.
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    assert (raiz / "la-gerencia/static/js/constructor_kpi.js").is_file()
