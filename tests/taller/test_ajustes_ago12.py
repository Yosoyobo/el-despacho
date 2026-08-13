"""LC 2026-08-12 — notas de Oscar sobre el deploy del 8 de agosto.

Cubre el ticket:

* Un solo motor de arrastre para TODO El Taller (antes eran seis, y cuatro de
  ellos no existían en pantalla táctil — de ahí que el tablero de tareas «no
  fuera arrastrable» desde el celular).
* El alta abre el modal moderno desde cualquier lista, no la página vieja.
* El buscador del Dashboard alcanza los proyectos entregados y cerrados.
* Guardar te deja donde estás; archivar desde una lista te devuelve con tus
  filtros puestos.
* Con un solo producto, el documento se titula «Producción de [Producto]».
* La tarjeta de producto: «+ Agregar producto» y Cant./Merma sin encimarse.
* La calculadora de Simil actualiza los proyectos vivos.
* La página de Productos abre en fichas.
* El costo unitario acepta cuentas: `15.75*100`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.taller]

JS_ARRASTRE = Path("el-taller/static/js/arrastrar.js")
TPL_BASE = Path("el-taller/templates/base.html")

# Las pantallas que antes tenían su propio motor: (dónde está la zona, dónde el
# elemento). En dos de ellas la tarjeta vive en su propio partial.
ZONAS = {
    "tablero de tareas": (
        Path("el-taller/templates/pizarron/kanban.html"),
        Path("el-taller/templates/pizarron/_kanban_tarjeta.html"),
    ),
    "tablero de proyectos": (
        Path("el-taller/templates/proyectos/_kanban_columna.html"),
    ) * 2,
    "filas de tareas (proyecto)": (
        Path("el-taller/templates/proyectos/_tareas_panel.html"),
    ) * 2,
    "filas de tareas (lista)": (
        Path("el-taller/templates/pizarron/lista.html"),
    ) * 2,
    "tarjetas de producto": (
        Path("el-taller/templates/proyectos/detalle.html"),
        Path("el-taller/templates/proyectos/_producto_card.html"),
    ),
    "calendario": (Path("el-taller/templates/calendario/_mes.html"),) * 2,
    "KPIs del tablero": (Path("el-taller/templates/taller_home/home.html"),) * 2,
    "carpetas del menú": (
        Path("el-taller/templates/taller_home/sidebar_preferencias.html"),
    ) * 2,
}

# Los que se borraron al unificar.
MOTORES_RETIRADOS = [
    Path("el-taller/templates/pizarron/_kanban_script_tareas.html"),
    Path("el-taller/templates/pizarron/_tareas_orden_js.html"),
]


# ── El motor ─────────────────────────────────────────────────────────────────


def test_el_motor_existe_y_lo_carga_el_taller():
    assert JS_ARRASTRE.exists(), "falta static/js/arrastrar.js"
    assert "js/arrastrar.js" in TPL_BASE.read_text(encoding="utf-8")


def test_el_motor_usa_pointer_events_y_no_el_arrastre_de_html5():
    """Es LA razón del sprint: el drag & drop de HTML5 no existe en táctil."""
    js = JS_ARRASTRE.read_text(encoding="utf-8")
    for gesto in ("pointerdown", "pointermove", "pointerup", "pointercancel"):
        assert gesto in js, f"el motor no escucha {gesto}"
    for viejo in ("dragstart", "dragover", "dragend", "dataTransfer"):
        assert viejo not in js, f"el motor todavía usa {viejo} (HTML5, sin dedo)"


def test_el_motor_espera_un_umbral_para_no_comerse_los_clics():
    """Las tarjetas del Kanban son enlaces: picarlas tiene que seguir abriendo."""
    js = JS_ARRASTRE.read_text(encoding="utf-8")
    assert "UMBRAL" in js
    assert "if (!hubo) return;" in js, "sin umbral, un clic se tomaría como arrastre"


def test_el_motor_se_reengancha_tras_un_swap_de_htmx():
    assert "htmx:afterSwap" in JS_ARRASTRE.read_text(encoding="utf-8")


@pytest.mark.parametrize("ruta", MOTORES_RETIRADOS, ids=lambda p: p.name)
def test_los_motores_viejos_ya_no_existen(ruta):
    assert not ruta.exists(), f"{ruta} debía borrarse al unificar"


@pytest.mark.parametrize("nombre,rutas", sorted(ZONAS.items()))
def test_cada_pantalla_declara_el_contrato_del_motor(nombre, rutas):
    zona, item = rutas
    assert "data-arr-zona" in zona.read_text(encoding="utf-8"), f"{nombre}: falta la zona"
    assert "data-arr-item" in item.read_text(encoding="utf-8"), (
        f"{nombre}: falta el elemento arrastrable"
    )


@pytest.mark.parametrize("nombre,rutas", sorted(ZONAS.items()))
def test_ninguna_pantalla_conserva_el_arrastre_viejo(nombre, rutas):
    for ruta in set(rutas):
        assert 'draggable="true"' not in ruta.read_text(encoding="utf-8"), (
            f"{nombre}: quedó un draggable de HTML5 en {ruta.name}"
        )


def test_el_tablero_de_tareas_mueve_de_columna_y_ordena_dentro():
    """Los dos defectos que reportó Oscar: no se arrastraba y no reordenaba."""
    texto = ZONAS["tablero de tareas"][0].read_text(encoding="utf-8")
    assert "data-arr-mover-url" in texto
    assert 'data-arr-mover-campo="estado"' in texto
    assert "data-arr-orden-url" in texto, "no guardaba el orden dentro de la columna"


def test_una_carpeta_del_menu_no_entra_en_otra_carpeta():
    texto = ZONAS["carpetas del menú"][0].read_text(encoding="utf-8")
    assert 'data-arr-acepta="item"' in texto
    assert 'data-arr-tipo="carpeta"' in texto


def test_el_calendario_y_los_productos_atienden_el_movimiento_ellos_mismos():
    """Los dos casos con lógica propia escuchan el evento del motor."""
    cal = Path("el-taller/templates/calendario/index.html").read_text(encoding="utf-8")
    assert "arrastrar:mover" in cal
    prods = Path("el-taller/templates/proyectos/_form_productos_js.html").read_text(encoding="utf-8")
    assert "arrastrar:ordenar" in prods
