"""S-KPIs-V2 en El Taller: metas proporcionales, tablero por rol, semáforo,
aviso de metas en riesgo y la foto diaria del dinero (2026-09-29)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.taller_home.metas import avance_periodo, clave_periodo, evaluar

# ── El juicio (función pura) ─────────────────────────────────────────────

D15 = date(2026, 9, 15)   # la mitad de un mes de 30 días


@pytest.mark.parametrize("numero, esperado", [
    (50, "en_camino"),      # la mitad a medio mes: va bien
    (44, "en_camino"),      # dentro de la tolerancia (15%)
    (40, "en_riesgo"),      # 40 < 50 × 0.85
    (100, "cumplida"),
    (120, "cumplida"),
])
def test_sube_y_acumula_se_mide_proporcional(numero, esperado):
    ev = evaluar(100, numero, direccion="sube", acumula="mes", hoy=D15)
    assert ev["estado"] == esperado
    assert ev["esperado"] == pytest.approx(50)


def test_al_principio_del_periodo_no_se_declara_riesgo():
    # Día 2: se esperaba 6.7, lleva 0; todavía no se juzga.
    assert evaluar(100, 0, acumula="mes", hoy=date(2026, 9, 2))["estado"] == "en_camino"
    assert evaluar(100, 0, acumula="mes", hoy=date(2026, 9, 7))["estado"] == "en_riesgo"


@pytest.mark.parametrize("numero, esperado", [
    (40, "en_camino"),      # gastó 40% del tope a medio mes
    (57, "en_camino"),      # 57 < 50 × 1.15
    (60, "en_riesgo"),      # gasta más rápido de lo sano
    (101, "excedida"),      # se pasó del tope
])
def test_baja_y_acumula_es_un_presupuesto(numero, esperado):
    assert evaluar(100, numero, direccion="baja", acumula="mes", hoy=D15)["estado"] == esperado


@pytest.mark.parametrize("numero, esperado", [
    (50, "cumplida"),       # saldo por debajo del tope
    (90, "en_riesgo"),      # pegado al tope
    (130, "excedida"),
])
def test_baja_saldo_al_corte(numero, esperado):
    assert evaluar(100, numero, direccion="baja", acumula="", hoy=D15)["estado"] == esperado


@pytest.mark.parametrize("numero, esperado", [
    (100, "cumplida"), (90, "en_camino"), (80, "en_riesgo"),
])
def test_sube_saldo_al_corte(numero, esperado):
    assert evaluar(100, numero, direccion="sube", acumula="", hoy=D15)["estado"] == esperado


def test_sin_numero_o_meta_en_cero_es_sin_datos():
    assert evaluar(100, None)["estado"] == "sin_datos"
    assert evaluar(0, 10)["estado"] == "sin_datos"


def test_avance_y_clave_de_periodo():
    assert avance_periodo("mes", D15) == pytest.approx(0.5)
    assert avance_periodo("semana", date(2026, 9, 28)) == pytest.approx(1 / 7)   # lunes
    assert avance_periodo("", D15) == 1.0
    assert clave_periodo("mes", D15) == "2026-09"
    assert clave_periodo("ano", D15) == "2026"
    assert clave_periodo("", D15) == "2026-S38"
    assert clave_periodo("dia", D15) == "2026-09-15"


# ── El semáforo ──────────────────────────────────────────────────────────

class _Cfg:
    def __init__(self, amarillo=None, rojo=None, direccion=""):
        self.umbral_amarillo = None if amarillo is None else Decimal(str(amarillo))
        self.umbral_rojo = None if rojo is None else Decimal(str(rojo))
        self.direccion = direccion


@pytest.mark.django_db
@pytest.mark.parametrize("slug, numero, cfg, esperado", [
    ("cxc-total", 50, _Cfg(80, 100), "verde"),          # baja: umbrales son techos
    ("cxc-total", 85, _Cfg(80, 100), "amarillo"),
    ("cxc-total", 100, _Cfg(80, 100), "rojo"),
    ("ingresos-mes", 50, _Cfg(80, 60), "rojo"),         # sube: umbrales son pisos
    ("ingresos-mes", 70, _Cfg(80, 60), "amarillo"),
    ("ingresos-mes", 90, _Cfg(80, 60), "verde"),
    ("ingresos-mes", 90, _Cfg(), ""),                   # sin umbrales no juzga
    ("ingresos-mes", 0, _Cfg(rojo=0), "rojo"),          # 0 es un umbral de verdad
    ("accesos-hoy", 5, _Cfg(1, 2), ""),                 # neutro no lleva semáforo
])
def test_semaforo(slug, numero, cfg, esperado):
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.tablero import semaforo

    assert semaforo(kpi_por_slug(slug), numero, cfg) == esperado


# ── El tablero ───────────────────────────────────────────────────────────



@pytest.mark.django_db
def test_el_por_omision_trae_los_ocho_de_siempre(usuario_factory):
    from apps.taller_home.tablero import kpis_del_tablero
    from apps.taller_home.views import COMPACT_KPI_SLUGS

    assert [k.slug for k in kpis_del_tablero(usuario_factory(rol="super_admin"))] == list(COMPACT_KPI_SLUGS)


@pytest.mark.django_db
def test_varios_roles_suman_sus_tableros_sin_repetir(usuario_factory):
    from apps.taller_home.models import TableroKPI
    from apps.taller_home.tablero import kpis_del_tablero

    from cuentas.models.rol import Rol

    a = Rol.objects.create(clave="a", nombre="A", permisos={"tesoreria": ["ver"]})
    b = Rol.objects.create(clave="b", nombre="B", permisos={"tesoreria": ["ver"], "cartera": ["ver"]})
    TableroKPI.objects.create(rol=a, kpi_slug="ingresos-mes", orden=0)
    TableroKPI.objects.create(rol=b, kpi_slug="ingresos-mes", orden=0)
    TableroKPI.objects.create(rol=b, kpi_slug="clientes-activos", orden=1)
    u = usuario_factory(rol="miembro")
    u.roles_extra.add(a, b)
    assert [k.slug for k in kpis_del_tablero(u)] == ["ingresos-mes", "clientes-activos"]


@pytest.mark.django_db
def test_lo_que_la_persona_quita_agrega_y_ordena(usuario_factory):
    from apps.taller_home.models import PreferenciaKPI
    from apps.taller_home.tablero import kpis_del_tablero

    u = usuario_factory(rol="super_admin")
    PreferenciaKPI.objects.create(usuario=u, kpi_slug="cxp-total", visible=False)
    PreferenciaKPI.objects.create(usuario=u, kpi_slug="margen-real", visible=True)
    PreferenciaKPI.objects.create(usuario=u, kpi_slug="cxc-total", visible=True, orden=0)
    slugs = [k.slug for k in kpis_del_tablero(u)]
    assert "cxp-total" not in slugs
    assert "margen-real" in slugs
    assert slugs[0] == "cxc-total"


@pytest.mark.django_db
def test_el_inicio_pinta_el_tablero_con_su_formato(client, usuario_factory):
    from apps.taller_home.models import TableroKPI

    TableroKPI.objects.filter(rol__isnull=True).delete()
    TableroKPI.objects.create(rol=None, kpi_slug="margen-real", orden=0)
    TableroKPI.objects.create(rol=None, kpi_slug="ingresos-mes", orden=1)
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    html = client.get("/").content.decode()
    assert 'data-arr-item="margen-real"' in html
    assert 'data-arr-item="ingresos-mes"' in html
    assert 'data-arr-item="cxp-total"' not in html    # ya no está fijo en el código


@pytest.mark.django_db
def test_la_meta_se_pinta_en_la_tarjeta(client, usuario_factory):
    from apps.taller_home.models import MetaKPI

    MetaKPI.objects.create(kpi_slug="ingresos-mes", valor=Decimal("250000"), periodo="mes")
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get("/").content.decode()
    assert "Meta $250,000" in html


@pytest.mark.django_db
def test_reordenar_no_cuela_slugs_ajenos(client, usuario_factory):
    from apps.taller_home.models import PreferenciaKPI

    u = usuario_factory(rol="disenador")
    client.force_login(u)
    client.post("/perfil/dashboard/reordenar", {"slugs": ["ingresos-mes", "no-existe"]})
    assert not PreferenciaKPI.objects.filter(usuario=u, kpi_slug__in=["ingresos-mes", "no-existe"]).exists()


# ── Metas: persona y cliente ─────────────────────────────────────────────

@pytest.mark.django_db
def test_meta_de_persona_se_mide_con_su_numero(usuario_factory):
    from apps.taller_home.metas import estado_de_metas
    from apps.taller_home.models import MetaKPI

    u = usuario_factory(rol="disenador")
    MetaKPI.objects.create(kpi_slug="mis-tareas-vencidas", ambito="persona", usuario=u,
                           valor=Decimal("3"), periodo="corte")
    fila = estado_de_metas()[0]
    assert fila["numero"] == 0 and fila["quien"] == u.nombre_completo
    assert fila["evaluacion"]["estado"] == "cumplida"     # baja: 0 ≤ 3


@pytest.mark.django_db
def test_meta_de_cliente_usa_el_desglose(cliente_factory):
    from apps.taller_home import metas
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.models import MetaKPI

    kpi = next(k for k in __import__("apps.taller_home.kpis", fromlist=["KPIS"]).KPIS
               if "cliente" in k.desgloses)
    c = cliente_factory()
    meta = MetaKPI.objects.create(kpi_slug=kpi.slug, ambito="cliente", cliente=c,
                                  valor=Decimal("1000"), periodo=metas.periodo_de(kpi))

    class _Calc(metas._Calculadora):
        def desglose(self, kpi, ambito):
            return {c.pk: 400.0}

    assert metas.numero_de_meta(meta, kpi_por_slug(kpi.slug), _Calc()) == 400.0


# ── El aviso ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_se_avisa_una_sola_vez_por_periodo(usuario_factory, monkeypatch):
    from apps.taller_home import metas
    from apps.taller_home.models import MetaKPI

    admin = usuario_factory(rol="super_admin")
    usuario_factory(rol="disenador")    # no configura KPIs: no le llega
    enviados = []
    monkeypatch.setattr("lib.interfono.enviar_a_usuario",
                        lambda u, titulo, cuerpo, **kw: enviados.append((u.pk, titulo, kw)))
    meta = MetaKPI.objects.create(kpi_slug="ingresos-mes", valor=Decimal("250000"), periodo="mes")
    hoy = date(2026, 9, 20)

    primera = metas.avisar_en_riesgo(hoy=hoy)
    assert [a["meta_id"] for a in primera] == [meta.pk]
    assert [e[0] for e in enviados] == [admin.pk]
    assert enviados[0][2]["categoria"] == "metas_kpi"
    meta.refresh_from_db()
    assert meta.avisado_periodo == "2026-09"

    assert metas.avisar_en_riesgo(hoy=hoy + timedelta(days=1)) == []   # mismo periodo
    assert len(metas.avisar_en_riesgo(hoy=date(2026, 10, 20))) == 1       # periodo nuevo


@pytest.mark.django_db
def test_meta_de_persona_le_avisa_a_esa_persona(usuario_factory, monkeypatch):
    from apps.taller_home import metas
    from apps.taller_home.models import MetaKPI

    usuario_factory(rol="super_admin")
    persona = usuario_factory(rol="disenador")
    enviados = []
    monkeypatch.setattr("lib.interfono.enviar_a_usuario",
                        lambda u, *a, **kw: enviados.append(u.pk))
    MetaKPI.objects.create(kpi_slug="checador-horas-semana", ambito="persona", usuario=persona,
                           valor=Decimal("40"), periodo="semana")
    metas.avisar_en_riesgo(hoy=date(2026, 10, 2))   # viernes: 5/7 de semana, 0 horas
    assert enviados == [persona.pk]


@pytest.mark.django_db
def test_el_dry_run_no_manda_ni_marca(usuario_factory, monkeypatch):
    from apps.taller_home import metas
    from apps.taller_home.models import MetaKPI

    usuario_factory(rol="super_admin")
    monkeypatch.setattr("lib.interfono.enviar_a_usuario",
                        lambda *a, **kw: pytest.fail("no debió mandar"))
    meta = MetaKPI.objects.create(kpi_slug="ingresos-mes", valor=Decimal("250000"), periodo="mes")
    assert len(metas.avisar_en_riesgo(hoy=date(2026, 9, 20), dry_run=True)) == 1
    meta.refresh_from_db()
    assert meta.avisado_periodo == ""


# ── La foto diaria ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_la_foto_diaria_guarda_el_dinero_y_se_salta_lo_personal(usuario_factory):
    from django.core.management import call_command

    from apps.taller_home.models import SnapshotKPI

    usuario_factory(rol="super_admin")
    call_command("kpi_foto_diaria")
    slugs = set(SnapshotKPI.objects.values_list("kpi_slug", flat=True))
    assert "ingresos-mes" in slugs          # antes «$0» era texto y se saltaba
    assert "cxc-total" in slugs
    assert "checador-horas-semana" not in slugs
    assert "mis-tareas-vencidas" not in slugs


@pytest.mark.django_db
def test_lo_apagado_no_se_fotografia(usuario_factory):
    from django.core.management import call_command

    from apps.taller_home.models import ConfigKPI, SnapshotKPI

    usuario_factory(rol="super_admin")
    ConfigKPI.objects.create(kpi_slug="ingresos-mes", activo=False)
    call_command("kpi_foto_diaria")
    assert not SnapshotKPI.objects.filter(kpi_slug="ingresos-mes").exists()


# ── La historia de lo que acumula ────────────────────────────────────────

@pytest.mark.django_db
def test_lo_que_acumula_se_compara_con_el_mismo_dia_del_periodo_anterior():
    from apps.taller_home import series
    from apps.taller_home.kpis import kpi_por_slug

    hoy = date.today()
    series.guardar("ingresos-mes", 100, dia=series._mes_anterior(hoy))
    juicio = series.juzgar(kpi_por_slug("ingresos-mes"), 150)
    assert juicio["comparacion"]["cambio_pct"] == 50.0
    assert juicio["anomalia"]["raro"] is False   # su juez es la meta, no la mediana


# ── Las migraciones de datos ─────────────────────────────────────────────

@pytest.mark.django_db
def test_la_limpieza_de_preferencias_respeta_lo_que_la_persona_decidio(usuario_factory):
    import importlib

    from django.apps import apps as django_apps

    from apps.taller_home.models import PreferenciaKPI

    mig = importlib.import_module("apps.taller_home.migrations.0007_sembrar_tablero_omision")
    u = usuario_factory(rol="dueno")
    for slug, visible, origen in [
        ("buzon-sugerencias", True, "manual"),        # del «guardar todo»: se va
        ("buzon-bugs-abiertos", False, "manual"),     # oculto a propósito: se queda
        ("ingresos-mes", True, "manual"),             # de los ocho: se queda
        ("hero-ingresos", True, "hero"),              # zona grande: se queda
        ("margen-real", True, "sugerido_chalan"),     # aceptó una sugerencia: se queda
        ("custom-lo-mio", True, "manual"),            # KPI del Chalán: se queda
    ]:
        PreferenciaKPI.objects.create(usuario=u, kpi_slug=slug, visible=visible, origen=origen)
    mig.sembrar(django_apps, None)
    quedan = set(PreferenciaKPI.objects.filter(usuario=u).values_list("kpi_slug", flat=True))
    assert quedan == {"buzon-bugs-abiertos", "ingresos-mes", "hero-ingresos", "margen-real", "custom-lo-mio"}


@pytest.mark.django_db
def test_kpis_configurar_se_siembra_como_hoy(usuario_factory):
    import importlib

    from django.apps import apps as django_apps

    from cuentas.models.permiso_usuario import PermisoUsuario
    from cuentas.models.rol import Rol

    mig = importlib.import_module("cuentas.migrations.0054_seed_permiso_kpis")
    sa = usuario_factory(rol="super_admin")
    con_ajustes = usuario_factory(rol="dueno")
    revocado = usuario_factory(rol="dueno")
    nadie = usuario_factory(rol="dueno")
    PermisoUsuario.objects.update_or_create(usuario=con_ajustes, modulo="ajustes", permiso="acceder",
                                            defaults={"activo": True})
    PermisoUsuario.objects.update_or_create(usuario=revocado, modulo="ajustes", permiso="acceder",
                                            defaults={"activo": False})
    rol = Rol.objects.create(clave="admin-x", nombre="Admin X", permisos={"ajustes": ["acceder"]})
    por_rol = usuario_factory(rol="miembro")
    por_rol.roles_extra.add(rol)
    PermisoUsuario.objects.filter(modulo="kpis").delete()

    mig.sembrar(django_apps, None)
    con = set(PermisoUsuario.objects.filter(modulo="kpis", permiso="configurar", activo=True)
              .values_list("usuario_id", flat=True))
    assert {sa.pk, con_ajustes.pk, por_rol.pk} <= con
    assert revocado.pk not in con and nadie.pk not in con
    rol.refresh_from_db()
    assert rol.permisos["kpis"] == ["configurar"]
