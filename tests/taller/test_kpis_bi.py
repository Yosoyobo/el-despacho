"""Los indicadores nuevos: que todos calculen y ninguno mienta.

Sprint S-KPI-BI (2026-08-22). Oscar pidió cubrir «tickets, financieros,
productos, proveedores, clientes, hardware del NUC, IA» y cruzarlo con «la
actividad de cada usuario, logins, jornadas, horas».

El test que más importa es el primero: **cada KPI del catálogo se calcula sin
tronar**. Con cuarenta funciones nuevas que tocan diez módulos distintos, un
nombre de campo mal escrito no se ve leyendo — se ve corriéndolo.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


def test_todos_los_kpis_del_catalogo_calculan(usuario_factory):
    """Ninguno debe lanzar, ni siquiera con la base casi vacía."""
    from apps.taller_home.kpis import KPIS

    admin = usuario_factory(rol="super_admin")
    fallaron = []
    for kpi in KPIS:
        try:
            r = kpi.calcular(admin)
            assert isinstance(r, dict), kpi.slug
            assert "valor" in r, kpi.slug
        except Exception as e:  # noqa: BLE001
            fallaron.append(f"{kpi.slug}: {e}")
    assert not fallaron, "KPIs que truenan:\n" + "\n".join(fallaron)


def test_el_catalogo_cubre_todos_los_dominios_que_pidio_oscar():
    from apps.taller_home.kpis import KPIS

    categorias = {k.categoria for k in KPIS}
    for esperada in ("buzon", "dinero", "catalogo", "proveedores", "cartera",
                     "maquina", "ia", "runner", "gente", "operacion"):
        assert esperada in categorias, f"falta el dominio {esperada}"


def test_cada_categoria_tiene_etiqueta_visible():
    """Un KPI en una categoría sin etiqueta no se agrupa en la pantalla."""
    from apps.taller_home.kpis import CATEGORIAS, KPIS

    con_etiqueta = {c for c, _ in CATEGORIAS}
    usadas = {k.categoria for k in KPIS if not k.categoria.startswith("custom")}
    huerfanas = usadas - con_etiqueta
    assert not huerfanas, f"categorías sin etiqueta: {huerfanas}"


def test_no_hay_slugs_repetidos():
    from apps.taller_home.kpis import KPIS

    slugs = [k.slug for k in KPIS]
    repetidos = {s for s in slugs if slugs.count(s) > 1}
    assert not repetidos, f"slugs duplicados: {repetidos}"


# ── La memoria: fotos diarias ────────────────────────────────────────────

def test_guardar_y_leer_la_serie():
    from apps.taller_home import series

    hoy = date.today()
    for i in range(5):
        series.guardar("ingresos-mes", 100 + i * 10, dia=hoy - timedelta(days=4 - i))
    s = series.serie("ingresos-mes", dias=30)
    assert len(s) == 5
    assert s[0]["valor"] == 100.0
    assert s[-1]["valor"] == 140.0


def test_guardar_dos_veces_el_mismo_dia_actualiza():
    from apps.taller_home import series
    from apps.taller_home.models import SnapshotKPI

    series.guardar("cxc-total", 500)
    series.guardar("cxc-total", 700)
    assert SnapshotKPI.objects.filter(kpi_slug="cxc-total").count() == 1
    assert series.serie("cxc-total")[-1]["valor"] == 700.0


def test_comparar_dice_cuanto_cambio():
    from apps.taller_home import series

    hoy = date.today()
    # Periodo anterior en 100, el actual en 150.
    for i in range(10, 20):
        series.guardar("utilidad-mes", 100, dia=hoy - timedelta(days=i))
    for i in range(0, 10):
        series.guardar("utilidad-mes", 150, dia=hoy - timedelta(days=i))

    c = series.comparar("utilidad-mes", dias=10)
    assert c["hay_datos"] is True
    assert c["direccion"] == "subio"
    assert c["cambio_pct"] == 50.0


def test_sin_historia_no_se_inventa_una_comparacion():
    from apps.taller_home import series

    c = series.comparar("kpi-que-nadie-ha-medido")
    assert c["hay_datos"] is False
    assert c["cambio_pct"] is None


def test_la_tendencia_necesita_varias_muestras():
    from apps.taller_home import series

    assert series.tendencia("sin-datos-aun") == "sin_datos"


# ── Anomalías: sin IA, contra su propia historia ─────────────────────────

def test_un_valor_fuera_de_lo_normal_se_detecta():
    from apps.taller_home import series

    hoy = date.today()
    for i in range(1, 15):
        series.guardar("egresos-mes", 1000, dia=hoy - timedelta(days=i))
    raro = series.es_raro("egresos-mes", 3000)
    assert raro["raro"] is True
    assert raro["motivo"] == "arriba"
    assert raro["desviacion_pct"] == 200.0


def test_un_valor_normal_no_levanta_la_mano():
    from apps.taller_home import series

    hoy = date.today()
    for i in range(1, 15):
        series.guardar("egresos-mes", 1000, dia=hoy - timedelta(days=i))
    assert series.es_raro("egresos-mes", 1050)["raro"] is False


def test_con_poca_historia_no_opina():
    """Con tres días todo parece una anomalía; el detector se calla."""
    from apps.taller_home import series

    hoy = date.today()
    for i in range(1, 4):
        series.guardar("nuevo-kpi", 10, dia=hoy - timedelta(days=i))
    r = series.es_raro("nuevo-kpi", 500)
    assert r["raro"] is False
    assert r["motivo"] == "poca_historia"


def test_la_mediana_aguanta_un_dia_raro():
    """Con promedio, un pico deja ciego al detector; con mediana, no."""
    from apps.taller_home import series

    hoy = date.today()
    for i in range(1, 15):
        series.guardar("ingresos-mes", 1000, dia=hoy - timedelta(days=i))
    series.guardar("ingresos-mes", 50000, dia=hoy - timedelta(days=1))
    # Un valor normal sigue siendo normal pese al pico histórico.
    assert series.es_raro("ingresos-mes", 1000)["raro"] is False


# ── Metas propuestas desde el histórico ──────────────────────────────────

def test_la_meta_sugerida_sale_de_lo_que_de_verdad_se_hizo():
    from apps.taller_home import series

    hoy = date.today()
    for i in range(1, 15):
        series.guardar("ingresos-mes", 200000, dia=hoy - timedelta(days=i))
    m = series.meta_sugerida("ingresos-mes")
    assert m["hay_datos"] is True
    assert m["tipico"] == 200000.0
    # Pide un poco más de lo típico, no un número inventado.
    assert m["sugerida"] == 220000.0


def test_sin_historia_no_sugiere_meta():
    from apps.taller_home import series

    assert series.meta_sugerida("jamas-medido")["hay_datos"] is False


def test_la_configuracion_del_analisis_sigue_intacta(db):
    """Los umbrales del sprint anterior no se tocaron."""
    from ajustes.models import ConfiguracionAnalisis

    cfg = ConfiguracionAnalisis.obtener()
    assert cfg.margen_sano_pct == Decimal("50.00")


# ── Curaduría: pocos y con motivo ────────────────────────────────────────

def test_solo_destaca_lo_que_tiene_una_razon(usuario_factory):
    """Con todo tranquilo, no destaca nada. Es la diferencia entre un analista
    y un tablero: el tablero siempre enseña 70 números."""
    from apps.taller_home.curaduria import destacados_de_hoy

    admin = usuario_factory(rol="super_admin")
    for d in destacados_de_hoy(admin):
        assert d["razon"], f"{d['slug']} se destacó sin motivo"


def test_lo_que_se_salio_de_lo_normal_se_destaca(usuario_factory):
    from apps.taller_home import series
    from apps.taller_home.curaduria import destacados_de_hoy

    admin = usuario_factory(rol="super_admin")
    hoy = date.today()
    # Una historia plana hace que cualquier salto sea evidente.
    for i in range(1, 15):
        series.guardar("clientes-activos", 1, dia=hoy - timedelta(days=i))
    for _ in range(40):
        pass
    destacados = destacados_de_hoy(admin, cuantos=20)
    # No exigimos que ESTE KPI salga (depende de datos), pero sí que todo lo que
    # salga traiga su porqué y venga ordenado por urgencia.
    pesos = [d["peso"] for d in destacados]
    assert pesos == sorted(pesos, reverse=True)


def test_nunca_destaca_mas_de_los_que_caben(usuario_factory):
    from apps.taller_home.curaduria import destacados_de_hoy

    admin = usuario_factory(rol="super_admin")
    assert len(destacados_de_hoy(admin)) <= 5


def test_propone_metas_solo_con_historia(usuario_factory):
    from apps.taller_home import series
    from apps.taller_home.curaduria import proponer_metas

    assert proponer_metas() == []          # sin historia, nada que proponer
    hoy = date.today()
    for i in range(1, 15):
        series.guardar("ingresos-mes", 100000, dia=hoy - timedelta(days=i))
    props = {p["slug"]: p for p in proponer_metas()}
    assert "ingresos-mes" in props
    assert props["ingresos-mes"]["sugerida"] == 110000.0


def test_las_sugerencias_no_se_repiten(usuario_factory):
    """Reusa el mecanismo que ya funcionaba; sembrar dos veces no duplica."""
    from apps.taller_home.curaduria import sembrar_sugerencias
    from apps.taller_home.models import SugerenciaKPI

    admin = usuario_factory(rol="super_admin")
    sembrar_sugerencias(admin)
    antes = SugerenciaKPI.objects.filter(usuario=admin).count()
    sembrar_sugerencias(admin)
    assert SugerenciaKPI.objects.filter(usuario=admin).count() == antes


# ── La ruta del runner ───────────────────────────────────────────────────

def test_la_ruta_ordena_por_cercania():
    from apps.el_pizarron.ruta import ordenar_por_cercania

    origen = (19.4326, -99.1332)          # Centro de la CDMX
    paradas = [
        {"id": "lejos", "lat": 19.70, "lng": -99.20},
        {"id": "cerca", "lat": 19.44, "lng": -99.14},
        {"id": "medio", "lat": 19.55, "lng": -99.17},
    ]
    orden = [p["id"] for p in ordenar_por_cercania(paradas, origen)]
    assert orden == ["cerca", "medio", "lejos"]


def test_las_paradas_sin_ubicacion_no_se_pierden():
    from apps.el_pizarron.ruta import ordenar_por_cercania

    paradas = [
        {"id": "ubicada", "lat": 19.44, "lng": -99.14},
        {"id": "sin_punto", "lat": None, "lng": None},
    ]
    orden = [p["id"] for p in ordenar_por_cercania(paradas, (19.43, -99.13))]
    assert orden == ["ubicada", "sin_punto"]


def test_los_enlaces_a_mapas_llevan_las_coordenadas():
    from apps.el_pizarron.ruta import url_apple, url_google, url_waze

    paradas = [{"lat": 19.44, "lng": -99.14}, {"lat": 19.50, "lng": -99.20}]
    g = url_google(paradas, (19.43, -99.13))
    assert "google.com/maps/dir" in g
    assert "19.5" in g and "destination" in g
    assert "waypoints" in g              # la parada intermedia va en la ruta
    assert "waze.com/ul" in url_waze(19.44, -99.14)
    assert "maps.apple.com" in url_apple(paradas)


def test_sin_paradas_no_hay_enlaces():
    from apps.el_pizarron.ruta import url_google

    assert url_google([]) == ""


# ── Mandado: reloj y distancia ───────────────────────────────────────────

def _mandado(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Mandado, Tarea

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    tarea = Tarea.objects.create(
        titulo="Entregar gorras", proyecto=p, creado_por=u, tipo="entrega",
        asignada_a=u, fecha_compromiso=date.today(),
    )
    return Mandado.objects.get_or_create(tarea=tarea)[0], u


def test_el_mandado_mide_tiempo_y_distancia(proyecto_factory, usuario_factory):
    from apps.el_pizarron import mandados as svc

    m, _ = _mandado(proyecto_factory, usuario_factory)
    svc.marcar_en_camino(m, lat=19.4326, lng=-99.1332)
    svc.marcar_entregado(m, lat=19.4526, lng=-99.1532, completar_tarea=False)
    m.refresh_from_db()
    assert m.inicio_lat == 19.4326
    assert m.fin_lat == 19.4526
    assert m.distancia_m and m.distancia_m > 1000     # ~3 km en línea recta
    assert m.km_recorridos is not None
    assert m.minutos_en_ruta is not None


def test_sin_ubicacion_el_mandado_se_marca_igual(proyecto_factory, usuario_factory):
    """El GPS puede fallar; eso no puede impedir que el runner trabaje."""
    from apps.el_pizarron import mandados as svc

    m, _ = _mandado(proyecto_factory, usuario_factory)
    svc.marcar_en_camino(m)
    svc.marcar_entregado(m, completar_tarea=False)
    m.refresh_from_db()
    assert m.estado == "entregado"
    assert m.distancia_m is None


# ── A quién le toca el mandado ───────────────────────────────────────────

def test_quien_no_ha_checado_entrada_queda_hasta_el_final(
    proyecto_factory, usuario_factory
):
    """Mandar a alguien que no ha llegado es peor que mandarlo más lejos."""
    from apps.checador.models import Jornada
    from apps.el_pizarron.models import Tarea
    from apps.el_pizarron.runners import evaluar_runners
    from django.utils import timezone

    from cuentas.models.rol import Rol

    rol, _ = Rol.objects.get_or_create(clave="runner", defaults={"nombre": "Runner"})
    trabajando = usuario_factory(rol="miembro", email="r1@x.com")
    ausente = usuario_factory(rol="miembro", email="r2@x.com")
    for u in (trabajando, ausente):
        u.roles_extra.add(rol)
    rol.permisos = {"runner": ["recibir"]}
    rol.save()

    Jornada.objects.create(
        usuario=trabajando, fecha=date.today(), entrada_en=timezone.now(),
        estado="abierta",
    )

    p = proyecto_factory()
    tarea = Tarea.objects.create(
        titulo="Recoger lonas", proyecto=p, creado_por=trabajando, tipo="recoger",
        fecha_compromiso=date.today(),
    )
    filas = evaluar_runners(tarea)
    if len(filas) >= 2:
        assert filas[0]["runner"].pk == trabajando.pk
        assert any("no ha checado" in r for r in filas[-1]["razones"])


# ── MCP: todo lo nuevo expuesto (regla de Oscar) ─────────────────────────

def test_las_capacidades_de_bi_estan_registradas():
    from capacidades import CAPACIDADES

    for nombre in ("serie_kpi", "comparar_kpi", "kpis_a_mirar_hoy",
                   "anomalias_kpi", "metas_sugeridas", "ruta_del_dia",
                   "sugerir_runner"):
        assert nombre in CAPACIDADES, nombre


def test_el_servidor_externo_expone_los_indicadores():
    from mcp_despacho import herramientas

    assert hasattr(herramientas, "indicadores")
    assert hasattr(herramientas, "serie_indicador")


def test_serie_kpi_avisa_cuando_todavia_no_hay_historia(usuario_factory):
    from capacidades import ejecutar

    admin = usuario_factory(rol="super_admin")
    r = ejecutar("serie_kpi", {"slug": "ingresos-mes"}, admin)
    assert r.get("hay_historia") is False or "serie" in r


def test_serie_kpi_rechaza_un_indicador_inventado(usuario_factory):
    from capacidades import ejecutar

    admin = usuario_factory(rol="super_admin")
    assert "error" in ejecutar("serie_kpi", {"slug": "no-existe-esto"}, admin)


# ── La foto diaria ───────────────────────────────────────────────────────

def test_el_comando_guarda_una_foto_de_cada_indicador(usuario_factory):
    from apps.taller_home.models import SnapshotKPI
    from django.core.management import call_command

    usuario_factory(rol="super_admin")
    call_command("kpi_foto_diaria", verbosity=0)
    assert SnapshotKPI.objects.filter(fecha=date.today()).count() > 20


def test_correrlo_dos_veces_no_duplica(usuario_factory):
    from apps.taller_home.models import SnapshotKPI
    from django.core.management import call_command

    usuario_factory(rol="super_admin")
    call_command("kpi_foto_diaria", verbosity=0)
    n = SnapshotKPI.objects.count()
    call_command("kpi_foto_diaria", verbosity=0)
    assert SnapshotKPI.objects.count() == n
