"""El constructor de KPIs en un navegador de verdad (S-KPIs-V2 · 2).

El formulario lo arma JavaScript desde el esquema del DSL: las pruebas de
vistas no ven si un clic produce la definición correcta. Aquí se arma un KPI
dando clics en Chromium (Playwright), se espera la vista previa, se guarda y
se reabre. Si no hay navegador instalado (el CI), se saltan.
Instalar: `.venv/bin/python -m playwright install chromium`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db(transaction=True)]

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def navegador(live_server, usuario_factory, settings, monkeypatch):
    """Una página con sesión de super_admin y el estático de La Gerencia."""
    from django.contrib.staticfiles import finders
    from django.test import Client

    # Playwright corre su propio bucle de eventos en este hilo.
    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    settings.STATICFILES_DIRS = [str(RAIZ / "la-gerencia/static")]
    finders.get_finder.cache_clear()
    cliente = Client()
    cliente.force_login(usuario_factory(rol="super_admin"))
    sesion = cliente.cookies[settings.SESSION_COOKIE_NAME].value
    with sync_api.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001 — sin Chromium instalado
            pytest.skip(f"sin navegador: {exc}")
        ctx = nav.new_context()
        ctx.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": sesion, "url": live_server.url}])
        pag = ctx.new_page()
        pag.errores = []
        pag.on("pageerror", lambda e: pag.errores.append(str(e)))
        yield pag, live_server.url
        nav.close()
    finders.get_finder.cache_clear()
    os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)


def _preview_con(pag, texto):
    pag.wait_for_function(
        f"document.querySelector('#constructor-preview').textContent.includes({texto!r})", timeout=10000,
    )


def test_armar_guardar_y_reabrir(navegador):
    from apps.taller_home.models import KPICustom

    pag, url = navegador
    pag.goto(url + "/ajustes/kpis/constructor/nuevo/")
    raiz = pag.locator("#constructor-kpi")
    assert raiz.locator("h3").count() >= 6
    raiz.locator("select").nth(0).select_option("ingreso")
    raiz.locator("select").nth(2).select_option("sum")
    pag.get_by_label("Repartir por").select_option("cliente")
    _preview_con(pag, "Suma del monto de los ingresos")
    raiz.get_by_text("+ Agregar condición").first.click()   # vacía: no debe guardarse
    pag.fill("#kpi-titulo", "Cobrado por cliente")
    pag.get_by_role("button", name="Crear KPI").click()
    pag.wait_for_url("**/ajustes/kpis/constructor/")

    k = KPICustom.objects.get()
    assert k.definicion_json["entidad"] == "ingreso"
    assert k.definicion_json["agregacion"] == "sum" and k.definicion_json["campo"] == "monto"
    assert k.definicion_json["agrupar_por"] == "cliente"
    assert k.definicion_json["filtros"] == []

    pag.goto(url + f"/ajustes/kpis/constructor/{k.pk}/")
    _preview_con(pag, "agrupado por cliente")
    assert pag.locator("#constructor-kpi select").nth(0).input_value() == "ingreso"
    pag.set_viewport_size({"width": 390, "height": 844})
    assert pag.evaluate("document.documentElement.scrollWidth") <= 390
    assert pag.errores == []


def test_porcentaje_a_tiempo_con_fecha_contra_fecha(navegador):
    from apps.taller_home.models import KPICustom

    pag, url = navegador
    pag.goto(url + "/ajustes/kpis/constructor/nuevo/")
    raiz = pag.locator("#constructor-kpi")
    raiz.locator("select").nth(0).select_option("tarea")
    pag.get_by_label("Resultado").select_option("porcentaje")

    def fila(seccion):
        return raiz.locator("section").nth(seccion).locator("div.grid").first

    raiz.locator("section").nth(2).get_by_text("+ Agregar condición").click()
    fila(2).locator("select").nth(0).select_option("completada_en")
    fila(2).locator("select").nth(1).select_option("vacio")
    fila(2).locator("select").nth(2).select_option("false")
    raiz.locator("section").nth(3).get_by_text("+ Agregar condición").click()
    fila(3).locator("select").nth(0).select_option("completada_en")
    fila(3).locator("select").nth(1).select_option("lte")
    fila(3).locator("select").nth(2).select_option("ref")
    fila(3).locator("select").nth(3).select_option("fecha_compromiso")
    _preview_con(pag, "Porcentaje de tareas")
    pag.fill("#kpi-titulo", "Tareas a tiempo")
    pag.get_by_role("button", name="Crear KPI").click()
    pag.wait_for_url("**/ajustes/kpis/constructor/")

    d = KPICustom.objects.get().definicion_json
    assert d["tipo"] == "porcentaje"
    assert d["filtros"] == [{"campo": "completada_en", "op": "vacio", "valor": False}]
    assert d["filtros_numerador"] == [{"campo": "completada_en", "op": "lte", "campo_ref": "fecha_compromiso"}]
    assert pag.errores == []
