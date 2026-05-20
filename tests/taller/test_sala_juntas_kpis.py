"""S2b.4 — La Sala de Juntas con catálogo de KPIs + preferencias granulares."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.django_db


# ── Catálogo y filtrado por rol ─────────────────────────────────────────────


def test_catalogo_kpis_tiene_al_menos_25_entradas():
    from apps.taller_home.kpis import KPIS
    assert len(KPIS) >= 25


def test_kpis_por_rol_admin_ve_mas_que_disenador(usuario_factory):
    from apps.taller_home.kpis import kpis_aplicables_a_rol
    admin = kpis_aplicables_a_rol("super_admin")
    dis = kpis_aplicables_a_rol("disenador")
    assert len(admin) > len(dis)


def test_kpi_buzon_solo_admin(usuario_factory):
    from apps.taller_home.kpis import kpi_por_slug
    kpi = kpi_por_slug("buzon-sin-responder")
    assert "super_admin" in kpi.roles_visible
    assert "disenador" not in kpi.roles_visible


def test_kpi_dinero_ya_no_es_pendiente_tesoreria():
    """S2b.3: los KPIs financieros leen de La Tesorería con estado_kpi='activo'."""
    from apps.taller_home.kpis import kpi_por_slug
    assert kpi_por_slug("ingresos-mes").estado_kpi == "activo"
    assert kpi_por_slug("egresos-mes").estado_kpi == "activo"
    assert kpi_por_slug("cxc-total").estado_kpi == "activo"
    assert kpi_por_slug("cxp-total").estado_kpi == "activo"


# ── Cálculos ─────────────────────────────────────────────────────────────


def test_kpi_proyectos_activos_cuenta_correctamente(usuario_factory, proyecto_factory):
    u = usuario_factory(rol="dueno")
    proyecto_factory(estado="en_diseno")
    proyecto_factory(estado="en_produccion")
    proyecto_factory(estado="prospecto")  # no debe contar
    proyecto_factory(estado="cancelado")  # no debe contar

    from apps.taller_home.kpis import kpi_por_slug
    valor = kpi_por_slug("proyectos-activos").calcular(u)["valor"]
    assert valor == 2


def test_kpi_mis_tareas_vencidas_solo_mias(usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Tarea
    u = usuario_factory(rol="disenador")
    otro = usuario_factory(rol="disenador")
    p = proyecto_factory()
    ayer = date.today() - timedelta(days=1)

    Tarea.objects.create(proyecto=p, titulo="mía vencida", asignada_a=u, fecha_compromiso=ayer)
    Tarea.objects.create(proyecto=p, titulo="ajena vencida", asignada_a=otro, fecha_compromiso=ayer)
    Tarea.objects.create(proyecto=p, titulo="mía completada", asignada_a=u, fecha_compromiso=ayer, estado="completada")

    from apps.taller_home.kpis import kpi_por_slug
    assert kpi_por_slug("mis-tareas-vencidas").calcular(u)["valor"] == 1


def test_kpi_buzon_sin_responder_cuenta_nuevos(usuario_factory):
    from buzon.models import MensajeBuzon
    autor = usuario_factory()
    u = usuario_factory(rol="dueno")
    MensajeBuzon.objects.create(autor=autor, tipo="sugerencia", asunto="A", cuerpo="x", estado="nuevo")
    MensajeBuzon.objects.create(autor=autor, tipo="problema", asunto="B", cuerpo="x", estado="respondido")

    from apps.taller_home.kpis import kpi_por_slug
    assert kpi_por_slug("buzon-sin-responder").calcular(u)["valor"] == 1


# ── Preferencias granulares ─────────────────────────────────────────────


def test_preferencia_oculta_kpi_del_dashboard(usuario_factory):
    from apps.taller_home.kpis import kpis_visibles_para
    from apps.taller_home.models import PreferenciaKPI
    u = usuario_factory(rol="dueno")
    PreferenciaKPI.objects.create(usuario=u, kpi_slug="proyectos-activos", visible=False)
    slugs_visibles = [kpi.slug for kpi, _ in kpis_visibles_para(u)]
    assert "proyectos-activos" not in slugs_visibles


def test_preferencia_default_opt_in(usuario_factory):
    from apps.taller_home.kpis import kpis_visibles_para
    u = usuario_factory(rol="dueno")
    slugs = [kpi.slug for kpi, _ in kpis_visibles_para(u)]
    # Sin preferencias persistidas, todos los aplicables aparecen.
    assert "proyectos-activos" in slugs
    assert "buzon-sin-responder" in slugs


def test_dashboard_preferencias_guarda_seleccion(client, usuario_factory):
    from apps.taller_home.models import PreferenciaKPI
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    # Solo marca 'proyectos-activos' → el resto queda oculto.
    resp = client.post("/perfil/dashboard/guardar", {"visible": ["proyectos-activos"]})
    assert resp.status_code == 302
    assert PreferenciaKPI.objects.filter(usuario=u, kpi_slug="proyectos-activos", visible=True).exists()
    assert PreferenciaKPI.objects.filter(usuario=u, kpi_slug="buzon-sin-responder", visible=False).exists()


def test_dashboard_preferencias_solo_modifica_kpis_del_rol(client, usuario_factory):
    """Diseñador no puede activar accidentalmente KPIs admin-only."""
    from apps.taller_home.models import PreferenciaKPI
    d = usuario_factory(rol="disenador")
    client.force_login(d)
    client.post("/perfil/dashboard/guardar", {"visible": ["buzon-sin-responder"]})
    # No se creó preferencia para un KPI fuera del rol del diseñador.
    assert not PreferenciaKPI.objects.filter(usuario=d, kpi_slug="buzon-sin-responder").exists()


# ── Sugerencias (Capa 2) ─────────────────────────────────────────────────


def test_sugerencia_se_crea_cuando_regla_dispara(usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Tarea
    from apps.taller_home.models import SugerenciaKPI
    from apps.taller_home.sugerencias import evaluar_y_persistir

    u = usuario_factory(rol="dueno")
    otro = usuario_factory(rol="disenador")
    p = proyecto_factory()
    ayer = date.today() - timedelta(days=1)
    for i in range(4):
        Tarea.objects.create(proyecto=p, titulo=f"t{i}", asignada_a=otro, fecha_compromiso=ayer)

    evaluar_y_persistir(u)
    assert SugerenciaKPI.objects.filter(usuario=u, kpi_slug="tareas-vencidas-equipo", estado="pendiente").exists()


def test_sugerencia_no_se_duplica(usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Tarea
    from apps.taller_home.models import SugerenciaKPI
    from apps.taller_home.sugerencias import evaluar_y_persistir

    u = usuario_factory(rol="dueno")
    otro = usuario_factory(rol="disenador")
    p = proyecto_factory()
    ayer = date.today() - timedelta(days=1)
    for i in range(4):
        Tarea.objects.create(proyecto=p, titulo=f"t{i}", asignada_a=otro, fecha_compromiso=ayer)

    evaluar_y_persistir(u)
    evaluar_y_persistir(u)
    assert SugerenciaKPI.objects.filter(usuario=u, kpi_slug="tareas-vencidas-equipo").count() == 1


def test_sugerencia_descartada_no_vuelve_a_aparecer(usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Tarea
    from apps.taller_home.models import SugerenciaKPI
    from apps.taller_home.sugerencias import evaluar_y_persistir

    u = usuario_factory(rol="dueno")
    otro = usuario_factory(rol="disenador")
    p = proyecto_factory()
    ayer = date.today() - timedelta(days=1)
    for i in range(4):
        Tarea.objects.create(proyecto=p, titulo=f"t{i}", asignada_a=otro, fecha_compromiso=ayer)

    evaluar_y_persistir(u)
    sug = SugerenciaKPI.objects.get(usuario=u, kpi_slug="tareas-vencidas-equipo")
    sug.estado = "descartada"
    sug.save()

    evaluar_y_persistir(u)
    # Sigue habiendo solo 1 (la descartada), no se creó una nueva.
    assert SugerenciaKPI.objects.filter(usuario=u, kpi_slug="tareas-vencidas-equipo").count() == 1


def test_aceptar_sugerencia_activa_kpi(client, usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Tarea
    from apps.taller_home.models import PreferenciaKPI, SugerenciaKPI

    u = usuario_factory(rol="dueno")
    otro = usuario_factory(rol="disenador")
    p = proyecto_factory()
    ayer = date.today() - timedelta(days=1)
    for i in range(4):
        Tarea.objects.create(proyecto=p, titulo=f"t{i}", asignada_a=otro, fecha_compromiso=ayer)

    client.force_login(u)
    client.get("/")  # dispara evaluar_y_persistir
    sug = SugerenciaKPI.objects.get(usuario=u, kpi_slug="tareas-vencidas-equipo")
    resp = client.post(f"/perfil/dashboard/sugerencia/{sug.pk}/aceptar")
    assert resp.status_code == 302
    sug.refresh_from_db()
    assert sug.estado == "aceptada"
    assert PreferenciaKPI.objects.filter(
        usuario=u, kpi_slug="tareas-vencidas-equipo", visible=True, origen="sugerido_chalan",
    ).exists()


# ── Sala de Juntas render ─────────────────────────────────────────────────


def test_home_renderiza_kpis_iterados(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Tu tablero" in html
    assert "Editar KPIs visibles" in html


def test_home_oculta_kpi_si_preferencia_lo_dice(client, usuario_factory):
    from apps.taller_home.models import PreferenciaKPI
    u = usuario_factory(rol="dueno")
    PreferenciaKPI.objects.create(usuario=u, kpi_slug="proyectos-activos", visible=False)
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    # El KPI no debe estar listado en el contexto.
    titulos = [k["titulo"] for k in resp.context["kpis"]]
    assert "Proyectos activos" not in titulos
