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


# ── El alta abre el modal desde cualquier lista ──────────────────────────────

ALTAS = {
    "proyectos (lista)": (Path("el-taller/templates/proyectos/lista.html"), "proyectos-nuevo"),
    "proyectos (tablero)": (Path("el-taller/templates/proyectos/kanban.html"), "proyectos-nuevo"),
    "clientes": (Path("el-taller/templates/cartera/lista.html"), "cartera-nuevo"),
    "productos": (Path("el-taller/templates/catalogo/lista.html"), "catalogo-nuevo"),
    "proveedores": (
        Path("el-taller/templates/catalogo/proveedores_lista.html"),
        "catalogo-proveedor-nuevo",
    ),
    "tesorería": (Path("el-taller/templates/tesoreria/landing.html"), "tesoreria:ingreso-nuevo"),
    "ingresos": (Path("el-taller/templates/tesoreria/ingresos_lista.html"), "tesoreria:ingreso-nuevo"),
    "egresos": (Path("el-taller/templates/tesoreria/egresos_lista.html"), "tesoreria:egreso-nuevo"),
    "tareas (lista)": (Path("el-taller/templates/pizarron/lista.html"), "/tareas/nueva/"),
    "tareas (tablero)": (Path("el-taller/templates/pizarron/kanban.html"), "/tareas/nueva/"),
}


@pytest.mark.parametrize("nombre,datos", sorted(ALTAS.items()))
def test_el_alta_de_cada_lista_abre_el_modal(nombre, datos):
    ruta, destino = datos
    texto = ruta.read_text(encoding="utf-8")
    assert 'hx-target="#modal-slot"' in texto, f"{nombre}: el alta no abre el modal"
    esperado = destino if destino.startswith("/") else f"{{% url '{destino}' %}}"
    assert f'hx-get="{esperado}"' in texto, f"{nombre}: el alta no apunta a {destino}"


@pytest.mark.parametrize("nombre,datos", sorted(ALTAS.items()))
def test_ninguna_lista_conserva_el_enlace_a_la_pagina_vieja(nombre, datos):
    ruta, destino = datos
    texto = ruta.read_text(encoding="utf-8")
    viejo = f'href="{destino}"' if destino.startswith("/") else f"<a href=\"{{% url '{destino}' %}}\" class=\"btn-"
    assert viejo not in texto, f"{nombre}: quedó el enlace a la página completa"


def test_el_empty_state_puede_abrir_el_modal_y_sigue_igual_en_las_dos_apps():
    taller = Path("el-taller/templates/_componentes_tailadmin/_empty_state.html")
    gerencia = Path("la-gerencia/templates/_componentes_tailadmin/_empty_state.html")
    texto = taller.read_text(encoding="utf-8")
    assert "cta_modal" in texto
    # Regla §18: las dos copias tienen que quedar idénticas.
    assert texto == gerencia.read_text(encoding="utf-8")


# ── El buscador del Dashboard alcanza los cerrados ───────────────────────────


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_user(
        email="jefa@lc.mx", password="x", rol="super_admin", nombre_completo="Jefa LC",
    )


@pytest.fixture
def cliente_nike():
    from apps.la_cartera.models import Cliente
    return Cliente.objects.create(razon_social="NIKE")


@pytest.mark.django_db
def test_la_busqueda_encuentra_lo_que_el_tablero_no_muestra(client, admin_user, cliente_nike):
    """El caso de Oscar: un proyecto entregado no está en las 4 columnas."""
    from apps.los_proyectos.models import Proyecto

    entregado = Proyecto.objects.create(
        nombre="Gorras Nike", cliente=cliente_nike, estado="entregado",
    )
    activo = Proyecto.objects.create(
        nombre="Bandanas Nike", cliente=cliente_nike, estado="en_proceso_diseno",
    )
    client.force_login(admin_user)
    html = client.get("/buscar/proyectos", {"q": "nike"}).content.decode()

    assert entregado.nombre in html, "el entregado tenía que salir"
    assert activo.nombre not in html, "el activo ya está en el tablero; no se repite"


@pytest.mark.django_db
def test_la_busqueda_tambien_alcanza_cerrados_y_cancelados(client, admin_user, cliente_nike):
    from apps.los_proyectos.models import Proyecto

    for estado in ("cerrado", "cancelado"):
        Proyecto.objects.create(
            nombre=f"Totes {estado}", cliente=cliente_nike, estado=estado,
        )
    client.force_login(admin_user)
    html = client.get("/buscar/proyectos", {"q": "totes"}).content.decode()
    assert "Totes cerrado" in html
    assert "Totes cancelado" in html


@pytest.mark.django_db
def test_la_busqueda_no_dispara_con_una_sola_letra(client, admin_user, cliente_nike):
    from apps.los_proyectos.models import Proyecto

    Proyecto.objects.create(nombre="Gorras", cliente=cliente_nike, estado="entregado")
    client.force_login(admin_user)
    assert "Gorras" not in client.get("/buscar/proyectos", {"q": "g"}).content.decode()


@pytest.mark.django_db
def test_la_busqueda_respeta_lo_que_cada_quien_puede_ver(client, django_user_model, cliente_nike):
    """Un miembro sin asignación no ve proyectos ajenos, tampoco al buscar."""
    from apps.los_proyectos.models import Proyecto

    ajeno = django_user_model.objects.create_user(
        email="dani@lc.mx", password="x", rol="miembro", nombre_completo="Dani",
    )
    Proyecto.objects.create(nombre="Gorras Nike", cliente=cliente_nike, estado="entregado")
    client.force_login(ajeno)
    assert "Gorras Nike" not in client.get("/buscar/proyectos", {"q": "nike"}).content.decode()


def test_el_buscador_del_dashboard_pega_al_servidor():
    home = Path("el-taller/templates/taller_home/home.html").read_text(encoding="utf-8")
    assert 'hx-target="#kanban-fuera"' in home
    assert 'id="kanban-fuera"' in home
