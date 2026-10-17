"""El producto de una tarjeta NUNCA cambia solo (ticket de Oscar, 14-oct-2026).

«Editando un proyecto, de repente se me flipearon unos valores en tarjetas de
producto: alias, costos, imágenes, etc. Esto NUNCA puede pasar.»

Alias, costo e imagen son lo que el JS vuelve a copiar del catálogo cuando el
`<select>` de producto dispara `change` (`prellenarServicio`). Esa copia pisa el
costo y el proveedor de la tarjeta con los del catálogo; lo único que la protege
es que `change` sólo ocurra cuando el usuario ELIGE en el panel buscable.
Pero un `<select>` enfocado cambia de valor con el teclado sin pasar por el panel
(escribir una letra = «type-ahead», flechas, Inicio/Fin, rueda) y eso dispara el
mismo `change`. Este test lo hace en Chromium de verdad: si la tarjeta cambia de
producto o pierde su costo, falla.

Se salta sin Chromium (el CI). Instalar: `.venv/bin/python -m playwright install chromium`.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

pytestmark = [pytest.mark.taller, pytest.mark.django_db(transaction=True)]

RAIZ = Path(__file__).resolve().parents[2]
NOMBRES = ["Almohada", "Bolsa", "Camiseta", "Delantal", "Etiqueta", "Gorra", "Hielera"]


@pytest.fixture
def navegador(live_server, usuario_factory, settings, monkeypatch):
    from django.contrib.staticfiles import finders
    from django.test import Client

    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    settings.STATICFILES_DIRS = [str(RAIZ / "el-taller/static")]
    finders.get_finder.cache_clear()
    cliente = Client()
    cliente.force_login(usuario_factory(rol="super_admin"))
    sesion = cliente.cookies[settings.SESSION_COOKIE_NAME].value
    with sync_api.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001 — sin Chromium instalado
            pytest.skip(f"sin navegador: {exc}")
        ctx = nav.new_context(viewport={"width": 1400, "height": 1000})
        ctx.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": sesion,
                          "url": live_server.url}])
        pag = ctx.new_page()
        pag.errores = []
        pag.on("pageerror", lambda e: pag.errores.append(str(e)))
        yield pag, live_server.url
        # Elegir un producto dispara el autoguardado del detalle (700 ms después):
        # si esa petición cae mientras Django vacía la base, el cierre truena con
        # «pop from empty list». Se deja la página en blanco y se espera a que el
        # servidor termine lo que tenga en curso antes de soltar la base.
        try:
            pag.goto("about:blank")
            pag.wait_for_timeout(1200)
        except Exception:  # noqa: BLE001 — el navegador ya se cerró
            pass
        ctx.close()
        nav.close()
    finders.get_finder.cache_clear()
    os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)


@pytest.fixture
def proyecto_con_dos_tarjetas(proyecto_factory):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    servicios = [
        Servicio.objects.create(nombre=n, precio_base="100", costo=str(10 * (i + 1)), categoria=cat)
        for i, n in enumerate(NOMBRES)
    ]
    p = proyecto_factory(nombre="Flip")
    # Costos puestos A MANO en la tarjeta: distintos de los del catálogo.
    a = ProyectoProducto.objects.create(
        proyecto=p, servicio=servicios[2], cantidad=1, orden=0,
        costo_unitario=Decimal("45.00"), nombre_proyecto="Playera staff")
    b = ProyectoProducto.objects.create(
        proyecto=p, servicio=servicios[4], cantidad=1, orden=1,
        costo_unitario=Decimal("99.00"), nombre_proyecto="Etiqueta tejida")
    return p, a, b, servicios


def _abrir_primera_tarjeta(pag, url, p):
    pag.goto(f"{url}/proyectos/{p.pk}/")
    pag.wait_for_selector("#formset-productos [data-card]")
    # Las tarjetas nacen colapsadas: se despliega la primera.
    pag.locator("#formset-productos [data-card-toggle]").first.click()
    sel = pag.locator('#formset-productos select[name$="-servicio"]').first
    sel.wait_for(state="visible")
    return sel


def _estado(pag):
    return pag.evaluate("""() => Array.from(
        document.querySelectorAll('#formset-productos [data-card]')).map(c => ({
          servicio: c.querySelector('select[name$="-servicio"]').value,
          costo: c.querySelector('input[name$="-costo_unitario"]').value,
          alias: (c.querySelector('[data-alias-input]') || {}).value || '',
        }))""")


@pytest.mark.parametrize("tecla", ["t", "H", "ArrowUp", "Home", "End", "PageDown"])
def test_el_teclado_no_cambia_el_producto_de_la_tarjeta(
        navegador, proyecto_con_dos_tarjetas, tecla):
    pag, url = navegador
    p, a, b, servicios = proyecto_con_dos_tarjetas
    sel = _abrir_primera_tarjeta(pag, url, p)
    antes = _estado(pag)
    sel.focus()
    pag.keyboard.press(tecla)
    pag.wait_for_timeout(300)
    # Si la tecla abrió el panel buscable, se cierra SIN elegir nada.
    pag.keyboard.press("Escape")
    pag.wait_for_timeout(300)
    assert _estado(pag) == antes, f"la tecla {tecla!r} cambió la tarjeta"
    assert not pag.errores


def test_elegir_en_el_panel_si_cambia_y_copia_el_catalogo(navegador, proyecto_con_dos_tarjetas):
    """El camino legítimo sigue funcionando: elegir un producto lo cambia."""
    pag, url = navegador
    p, a, b, servicios = proyecto_con_dos_tarjetas
    sel = _abrir_primera_tarjeta(pag, url, p)
    sel.click()
    pag.locator(".sb-panel li", has_text="Hielera").first.click()
    pag.wait_for_timeout(300)
    estado = _estado(pag)[0]
    assert estado["servicio"] == str(servicios[6].pk)
    assert Decimal(estado["costo"]) == Decimal(servicios[6].costo)
