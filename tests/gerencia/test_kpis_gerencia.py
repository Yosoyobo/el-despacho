"""La Gerencia → Ajustes → KPIs: catálogo, tableros por rol y metas (S-KPIs-V2).

Hasta 2026.09.13 guardar las metas daba 500 (la imagen no traía
`apps.taller_home`) y el panel salía vacío. Aquí se cuida el viaje completo de
las tres pestañas y su candado (`kpis.configurar`).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


@pytest.fixture
def admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin", email="kpis@x.com")
    client.force_login(u)
    return u


def _dar(usuario, modulo, permiso):
    from cuentas.models.permiso_usuario import PermisoUsuario

    PermisoUsuario.objects.update_or_create(
        usuario=usuario, modulo=modulo, permiso=permiso, defaults={"activo": True},
    )


# ── El candado ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("ruta", ["/ajustes/kpis/", "/ajustes/kpis/tableros/", "/ajustes/kpis/metas/"])
def test_las_pestanas_abren_para_quien_configura(client, admin, ruta):
    assert client.get(ruta).status_code == 200


@pytest.mark.parametrize("ruta", ["/ajustes/kpis/", "/ajustes/kpis/tableros/", "/ajustes/kpis/metas/"])
def test_sin_permiso_no_entra(client, usuario_factory, ruta):
    client.force_login(usuario_factory(rol="dueno"))
    assert client.get(ruta).status_code in (302, 403)


def test_el_permiso_se_delega_por_persona(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    _dar(u, "gerencia", "acceder")
    _dar(u, "kpis", "configurar")
    client.force_login(u)
    assert client.get("/ajustes/kpis/").status_code == 200


def test_la_url_vieja_de_metas_lleva_a_la_pestana(client, admin):
    resp = client.get("/ajustes/metas-kpi/")
    assert resp.status_code == 302 and resp["Location"].endswith("/ajustes/kpis/metas/")


def test_el_menu_ofrece_kpis_a_quien_solo_tiene_kpis(usuario_factory):
    from pathlib import Path

    from django.template import engines
    from django.test import RequestFactory

    menu = (Path(__file__).resolve().parents[2]
            / "la-gerencia/templates/_componentes_tailadmin/sidebar.html").read_text(encoding="utf-8")
    peticion = RequestFactory().get("/")
    peticion.user = usuario_factory(rol="dueno")
    plantilla = engines["django"].from_string(menu)
    solo_kpis = plantilla.render({"request": peticion, "permisos_modulos": {"kpis": True}})
    assert solo_kpis.count('href="/ajustes/kpis/"') == 1
    sin_kpis = plantilla.render({"request": peticion, "permisos_modulos": {"ajustes": True}})
    assert 'href="/ajustes/kpis/"' not in sin_kpis


# ── Catálogo ─────────────────────────────────────────────────────────────

def test_el_catalogo_lista_todos_los_kpis(client, admin):
    from apps.taller_home.kpis import KPIS

    html = client.get("/ajustes/kpis/").content.decode()
    for k in KPIS[:5] + KPIS[-3:]:
        assert f'id="kpi-{k.slug}"' in html


def test_apagar_un_kpi_lo_quita_de_todos_lados(client, admin, usuario_factory):
    from apps.taller_home.kpis import kpis_aplicables
    from apps.taller_home.tablero import kpis_del_tablero

    otro = usuario_factory(rol="super_admin")
    assert "ingresos-mes" in {k.slug for k in kpis_del_tablero(otro)}
    resp = client.post("/ajustes/kpis/catalogo/ingresos-mes/guardar",
                       {"direccion": "sube", "umbral_amarillo": "", "umbral_rojo": ""})
    assert resp.status_code == 302
    assert "ingresos-mes" not in {k.slug for k in kpis_aplicables(otro)}
    assert "ingresos-mes" not in {k.slug for k in kpis_del_tablero(otro)}


def test_guardar_direccion_y_umbrales(client, admin):
    from apps.taller_home.kpis import kpis_aplicables
    from apps.taller_home.models import ConfigKPI

    resp = client.post("/ajustes/kpis/catalogo/proyectos-activos/guardar",
                       {"activo": "1", "direccion": "baja", "umbral_amarillo": "10",
                        "umbral_rojo": "15"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200 and "Guardado" in resp.content.decode()
    cfg = ConfigKPI.objects.get(kpi_slug="proyectos-activos")
    assert (cfg.direccion, cfg.umbral_amarillo, cfg.umbral_rojo) == ("baja", Decimal("10"), Decimal("15"))
    efectivo = next(k for k in kpis_aplicables(admin) if k.slug == "proyectos-activos")
    assert efectivo.direccion == "baja"


def test_la_direccion_del_catalogo_no_se_guarda_como_propia(client, admin):
    from apps.taller_home.models import ConfigKPI

    client.post("/ajustes/kpis/catalogo/cxc-total/guardar", {"activo": "1", "direccion": "baja"})
    assert ConfigKPI.objects.get(kpi_slug="cxc-total").direccion == ""


def test_umbral_vacio_no_es_cero_y_texto_no_truena(client, admin):
    from apps.taller_home.models import ConfigKPI

    client.post("/ajustes/kpis/catalogo/cxc-total/guardar",
                {"activo": "1", "direccion": "baja", "umbral_amarillo": "0", "umbral_rojo": ""})
    cfg = ConfigKPI.objects.get(kpi_slug="cxc-total")
    assert cfg.umbral_amarillo == Decimal("0") and cfg.umbral_rojo is None
    resp = client.post("/ajustes/kpis/catalogo/cxc-total/guardar",
                       {"activo": "1", "umbral_rojo": "mucho"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200 and "no es un número" in resp.content.decode()
    cfg.refresh_from_db()
    assert cfg.umbral_amarillo == Decimal("0")   # el error no pisó lo guardado


def test_kpi_inexistente_o_direccion_invalida(client, admin):
    assert client.post("/ajustes/kpis/catalogo/no-existe/guardar", {}).status_code == 400
    assert client.post("/ajustes/kpis/catalogo/cxc-total/guardar",
                       {"direccion": "arriba"}).status_code == 400


# ── Tableros por rol ─────────────────────────────────────────────────────

def _rol(clave, permisos):
    from cuentas.models.rol import Rol

    return Rol.objects.create(clave=clave, nombre=clave.title(), permisos=permisos)


def test_el_tablero_del_rol_manda_sobre_el_por_omision(client, admin, usuario_factory):
    from apps.taller_home.tablero import kpis_del_tablero

    ventas = _rol("ventas", {"cotizaciones": ["ver"], "tesoreria": ["ver"]})
    persona = usuario_factory(rol="miembro")
    persona.roles_extra.add(ventas)
    antes = [k.slug for k in kpis_del_tablero(persona)]
    assert "cotizaciones-pendientes" in antes and "ingresos-mes" in antes  # el por omisión

    for slug in ("cotizaciones-aprobadas-mes", "ingresos-mes"):
        client.post("/ajustes/kpis/tableros/accion", {"rol": ventas.pk, "accion": "agregar", "slug": slug})
    assert [k.slug for k in kpis_del_tablero(persona)] == ["cotizaciones-aprobadas-mes", "ingresos-mes"]

    client.post("/ajustes/kpis/tableros/accion", {"rol": ventas.pk, "accion": "bajar",
                                                  "slug": "cotizaciones-aprobadas-mes"})
    assert [k.slug for k in kpis_del_tablero(persona)] == ["ingresos-mes", "cotizaciones-aprobadas-mes"]

    client.post("/ajustes/kpis/tableros/accion", {"rol": ventas.pk, "accion": "quitar", "slug": "ingresos-mes"})
    assert [k.slug for k in kpis_del_tablero(persona)] == ["cotizaciones-aprobadas-mes"]

    client.post("/ajustes/kpis/tableros/accion", {"rol": ventas.pk, "accion": "vaciar"})
    assert [k.slug for k in kpis_del_tablero(persona)] == antes


def test_el_tablero_nunca_ensena_lo_que_el_permiso_no_deja(client, admin, usuario_factory):
    from apps.taller_home.tablero import kpis_del_tablero

    diseno = _rol("diseno", {"proyectos": ["ver"], "pizarron": ["ver"]})
    persona = usuario_factory(rol="miembro")
    persona.roles_extra.add(diseno)
    client.post("/ajustes/kpis/tableros/accion", {"rol": diseno.pk, "accion": "agregar", "slug": "ingresos-mes"})
    assert "ingresos-mes" not in {k.slug for k in kpis_del_tablero(persona)}
    # Y la pantalla lo avisa.
    html = client.get(f"/ajustes/kpis/tableros/?rol={diseno.pk}").content.decode()
    assert "el rol no tiene su permiso" in html


def test_copiar_el_por_omision_y_htmx(client, admin):
    from apps.taller_home.tablero import base_de_rol

    rol = _rol("contabilidad", {"tesoreria": ["ver"]})
    resp = client.post("/ajustes/kpis/tableros/accion", {"rol": rol.pk, "accion": "copiar_omision"},
                       HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert base_de_rol(rol) == base_de_rol(None) and len(base_de_rol(rol)) == 8


def test_editar_el_tablero_por_omision(client, admin):
    from apps.taller_home.tablero import base_de_rol

    client.post("/ajustes/kpis/tableros/accion", {"rol": "omision", "accion": "agregar", "slug": "margen-real"})
    assert base_de_rol(None)[-1] == "margen-real"
    assert client.post("/ajustes/kpis/tableros/accion",
                       {"rol": "omision", "accion": "vaciar"}).status_code == 400
    assert client.post("/ajustes/kpis/tableros/accion",
                       {"rol": "omision", "accion": "agregar", "slug": "no-existe"}).status_code == 400


# ── Metas ────────────────────────────────────────────────────────────────

def test_crear_meta_del_despacho_y_verla(client, admin):
    from apps.taller_home.models import MetaKPI

    resp = client.post("/ajustes/kpis/metas/crear",
                       {"kpi_slug": "ingresos-mes", "ambito": "despacho", "valor": "250,000"})
    assert resp.status_code == 302
    meta = MetaKPI.objects.get(kpi_slug="ingresos-mes", ambito="despacho")
    assert meta.valor == Decimal("250000") and meta.periodo == "mes" and meta.actualizado_por == admin
    html = client.get("/ajustes/kpis/metas/").content.decode()
    assert "Ingresos del mes" in html and "$250,000" in html

    # Volver a crearla la actualiza (una sola meta del despacho por KPI).
    client.post("/ajustes/kpis/metas/crear", {"kpi_slug": "ingresos-mes", "ambito": "despacho", "valor": "300000"})
    assert MetaKPI.objects.filter(kpi_slug="ingresos-mes", ambito="despacho").count() == 1


def test_meta_de_persona_en_un_kpi_personal(client, admin, usuario_factory):
    from apps.taller_home.models import MetaKPI

    persona = usuario_factory(rol="disenador")
    client.post("/ajustes/kpis/metas/crear", {"kpi_slug": "checador-horas-semana", "ambito": "persona",
                                              "usuario": persona.pk, "valor": "40"})
    meta = MetaKPI.objects.get(kpi_slug="checador-horas-semana")
    assert meta.usuario == persona and meta.periodo == "semana"


@pytest.mark.parametrize("datos", [
    {"kpi_slug": "mis-tareas-vencidas", "ambito": "despacho", "valor": "1"},   # personal: no del despacho
    {"kpi_slug": "ingresos-mes", "ambito": "cliente", "valor": "1"},          # no se reparte por cliente
    {"kpi_slug": "accesos-hoy", "ambito": "despacho", "valor": "1"},          # sólo informa
    {"kpi_slug": "ingresos-mes", "ambito": "despacho", "valor": "0"},         # meta en cero
    {"kpi_slug": "ingresos-mes", "ambito": "despacho", "valor": "mucho"},
    {"kpi_slug": "checador-horas-semana", "ambito": "persona", "valor": "40"},  # sin persona
])
def test_metas_invalidas_no_se_guardan(client, admin, datos):
    from apps.taller_home.models import MetaKPI

    assert client.post("/ajustes/kpis/metas/crear", datos).status_code == 302
    assert not MetaKPI.objects.exists()


def test_editar_y_borrar_meta(client, admin):
    from apps.taller_home.models import MetaKPI

    meta = MetaKPI.objects.create(kpi_slug="egresos-mes", valor=Decimal("1000"), avisado_periodo="2026-09")
    client.post(f"/ajustes/kpis/metas/{meta.pk}/guardar", {"valor": "2000", "activa": "1"})
    meta.refresh_from_db()
    assert meta.valor == Decimal("2000") and meta.avisado_periodo == ""   # otra meta: se puede volver a avisar
    client.post(f"/ajustes/kpis/metas/{meta.pk}/guardar", {"valor": "2000"})
    meta.refresh_from_db()
    assert meta.activa is False
    client.post(f"/ajustes/kpis/metas/{meta.pk}/guardar", {"borrar": "1"})
    assert not MetaKPI.objects.filter(pk=meta.pk).exists()
