"""LC 2026-08-13 — notas de Oscar sobre el deploy del 12 de agosto.

Cubre el ticket de nueve puntos:

1. El arrastre volvió a servir en escritorio (lo secuestraba el arrastre nativo
   de los enlaces, que en táctil no existe — por eso sólo fallaba ahí).
2. Las miniaturas se quedan guardadas en el aparato un mes.
3. El aviso de «Sin guardar / ✓ Guardado» aplica a todas las páginas.
4. Los proveedores del modal de producto son un dropdown con buscador y
   palomitas, no una parrilla de casillas.
5. Todo dropdown de cliente / proveedor / producto / proyecto / contacto es el
   buscador que ya teníamos.
6. Lo que el buscador del Dashboard encuentra fuera del tablero se muestra en
   las mismas cuatro columnas, con su contador.
7. La página de Productos ordena por nombre, usos, costo, precio y margen.
8. Las fotos de las fichas se ven completas, no recortadas al cuadrado.
9. La tarjeta de producto vuelve a las medidas del render.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.taller]

JS_ARRASTRE = Path("el-taller/static/js/arrastrar.js")
JS_UI_TALLER = Path("el-taller/static/js/ui.js")
JS_UI_GERENCIA = Path("la-gerencia/static/js/ui.js")
JS_WIDGETS_TALLER = Path("el-taller/static/js/form_widgets.js")
JS_WIDGETS_GERENCIA = Path("la-gerencia/static/js/form_widgets.js")
TPL_CARD = Path("el-taller/templates/proyectos/_producto_card.html")
TPL_COLUMNA = Path("el-taller/templates/proyectos/_kanban_columna.html")
TPL_MODAL_PRODUCTO = Path("el-taller/templates/catalogo/_modal_nuevo_producto.html")
TPL_FICHAS = Path("el-taller/templates/catalogo/_tarjetas.html")
TPL_LISTA_CATALOGO = Path("el-taller/templates/catalogo/lista.html")


# ── 1. El arrastre en escritorio ─────────────────────────────────────────────


def test_el_motor_cancela_el_arrastre_nativo_del_navegador():
    """La causa del «ya no sirve en ningún lado»: las tarjetas del tablero son
    enlaces, y un enlace es arrastrable de fábrica. El navegador arrancaba SU
    arrastre, mandaba `pointercancel` y el nuestro moría. Con el dedo no pasa
    (no hay arrastre nativo), por eso sólo se caía en la computadora."""
    js = JS_ARRASTRE.read_text(encoding="utf-8")
    i = js.find("'dragstart'")
    assert i != -1, "el motor no cancela el arrastre nativo"
    trozo = js[i:i + 260]
    assert "preventDefault" in trozo
    assert "data-arr-item" in trozo, "cancela de más: sólo aplica dentro de un arrastrable"


def test_los_arrastrables_quedan_marcados_como_no_arrastrables_por_el_navegador():
    js = JS_ARRASTRE.read_text(encoding="utf-8")
    assert "'draggable', 'false'" in js


# ── 3. El aviso de cambios, en todas las páginas ─────────────────────────────


def test_el_aviso_de_cambios_ya_no_necesita_marcarse_pagina_por_pagina():
    """Antes sólo lo tenía la ficha de producto (`data-avisar-cambios`)."""
    js = JS_UI_TALLER.read_text(encoding="utf-8")
    assert "esFormDeGuardar" in js
    assert "data-sin-avisar-cambios" in js, "falta la puerta de salida"
    assert "#modal-slot" in js, "los modales no deben pedir confirmación al salir"


def test_la_barra_de_guardar_muestra_el_estado():
    js = JS_UI_TALLER.read_text(encoding="utf-8")
    for etiqueta in ("Sin guardar", "Guardando…", "✓ Guardado"):
        assert etiqueta in js, f"falta el estado «{etiqueta}»"
    assert "__guardarEstado" in js


def test_ui_js_sigue_siendo_dual_copy():
    """Regla §18: el archivo es idéntico en las dos apps."""
    assert JS_UI_TALLER.read_text(encoding="utf-8") == JS_UI_GERENCIA.read_text(encoding="utf-8")


# ── 4 y 5. Dropdowns ─────────────────────────────────────────────────────────


def test_existe_el_multi_select_con_buscador_y_palomitas():
    js = JS_WIDGETS_TALLER.read_text(encoding="utf-8")
    assert "data-multi-buscable" in js
    assert "multiBuscableRefrescar" in js, "falta la manija para el alta rápida y el 🤖"


def test_el_modal_de_producto_usa_el_dropdown_de_proveedores():
    """«Toma un exceso de espacio y es muy ineficiente» (Oscar)."""
    html = TPL_MODAL_PRODUCTO.read_text(encoding="utf-8")
    assert 'data-multi-buscable="proveedor"' in html
    assert 'id="prov-filtro"' not in html, "quedó el buscador viejo de la parrilla"
    assert "sm:grid-cols-2" not in html.split("proveedores-lista")[1][:200], \
        "la parrilla de dos columnas sigue ocupando la pantalla"
    # Las casillas siguen ahí (escondidas): el POST no cambió.
    assert "form.proveedores" in html


def test_los_dropdowns_de_entidades_se_reconocen_por_su_nombre():
    js = JS_WIDGETS_TALLER.read_text(encoding="utf-8")
    assert "CANONICOS" in js
    import re

    linea = next(ln for ln in js.splitlines() if ln.strip().startswith("var CANONICOS"))
    patron = re.search(r"/(.*)/i", linea).group(1)
    rx = re.compile(patron, re.I)
    for nombre in ("cliente", "items-0-servicio", "proveedor_principal", "proyecto",
                   "asignada_a", "runner", "cat-categoria", "contacto", "usuario"):
        assert rx.search(nombre), f"«{nombre}» debería ser un dropdown con buscador"
    for nombre in ("estado", "regimen_fiscal", "prioridad", "tipo"):
        assert not rx.search(nombre), f"«{nombre}» no es una entidad; sobra el buscador"


def test_form_widgets_sigue_siendo_dual_copy():
    assert JS_WIDGETS_TALLER.read_text(encoding="utf-8") == JS_WIDGETS_GERENCIA.read_text(encoding="utf-8")


# ── 6. El tablero inactivo del buscador ──────────────────────────────────────


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
def test_los_resultados_fuera_del_tablero_salen_en_las_cuatro_columnas(
    client, admin_user, cliente_nike,
):
    """«Que los muestre en los mismos recuadros de esas 4 categorías… el tablero
    inactivo que muestre 0, 0, 1 y 0 resultados» (Oscar)."""
    from apps.los_proyectos.models import Proyecto

    Proyecto.objects.create(nombre="Gorras Nike", cliente=cliente_nike, estado="entregado")
    client.force_login(admin_user)
    r = client.get("/buscar/proyectos", {"q": "gorras"})
    cols = r.context["cols"]

    assert [c["slug"] for c in cols] == ["en_pausa", "entregado", "cerrado", "cancelado"]
    assert [c["total"] for c in cols] == [0, 1, 0, 0]
    html = r.content.decode()
    assert "kanban-columna" in html, "no se reusó el recuadro canónico"
    assert "Gorras Nike" in html


@pytest.mark.django_db
def test_el_tablero_inactivo_no_se_arrastra(client, admin_user, cliente_nike):
    """Son resultados de búsqueda: moverlos de columna no tendría sentido."""
    from apps.los_proyectos.models import Proyecto

    Proyecto.objects.create(nombre="Totes viejos", cliente=cliente_nike, estado="cerrado")
    client.force_login(admin_user)
    html = client.get("/buscar/proyectos", {"q": "totes"}).content.decode()
    assert "data-arr-zona" not in html
    assert "kanban-columna-fuera" in html


@pytest.mark.django_db
def test_sin_resultados_no_se_pinta_el_tablero_inactivo(client, admin_user, cliente_nike):
    client.force_login(admin_user)
    html = client.get("/buscar/proyectos", {"q": "zzzz"}).content.decode()
    assert "kanban-columna" not in html
    assert "Nada más con" in html


def test_el_filtro_instantaneo_no_toca_las_columnas_del_servidor():
    js = Path("el-taller/templates/proyectos/_kanban_script.html").read_text(encoding="utf-8")
    assert ".kanban-columna:not(.kanban-columna-fuera)" in js


def test_la_columna_canonica_sigue_arrastrandose_por_default():
    """El modo `solo_lectura` es opt-in: la página Kanban no cambió."""
    html = TPL_COLUMNA.read_text(encoding="utf-8")
    assert "{% if not solo_lectura %}" in html
    assert "data-arr-zona" in html


# ── 7. Ordenar la página de Productos ────────────────────────────────────────


@pytest.fixture
def catalogo_surtido():
    from apps.el_catalogo.models import CategoriaServicio, Servicio

    cat = CategoriaServicio.objects.create(nombre="Textiles")
    Servicio.objects.create(nombre="Ancla", categoria=cat, precio_base=100, costo=90)
    Servicio.objects.create(nombre="Bandana", categoria=cat, precio_base=200, costo=20)
    Servicio.objects.create(nombre="Cinta", categoria=cat, precio_base=150, costo=75)
    return cat


@pytest.mark.django_db
@pytest.mark.parametrize(
    "orden, esperado",
    [
        ("nombre", ["Ancla", "Bandana", "Cinta"]),
        ("-nombre", ["Cinta", "Bandana", "Ancla"]),
        ("costo", ["Bandana", "Cinta", "Ancla"]),
        ("precio", ["Ancla", "Cinta", "Bandana"]),
        # Márgenes: Ancla 10 %, Cinta 50 %, Bandana 90 %.
        ("margen", ["Ancla", "Cinta", "Bandana"]),
        ("-margen", ["Bandana", "Cinta", "Ancla"]),
    ],
)
def test_la_lista_de_productos_ordena_por_cada_criterio(
    client, admin_user, catalogo_surtido, orden, esperado,
):
    client.force_login(admin_user)
    r = client.get("/catalogo/", {"orden": orden})
    assert [s.nombre for s in r.context["servicios"]] == esperado


@pytest.mark.django_db
def test_un_orden_inventado_no_tumba_la_pagina(client, admin_user, catalogo_surtido):
    """El whitelist evita un `order_by` arbitrario desde la URL."""
    client.force_login(admin_user)
    r = client.get("/catalogo/", {"orden": "costo); DROP TABLE"})
    assert r.status_code == 200
    assert [s.nombre for s in r.context["servicios"]] == ["Ancla", "Bandana", "Cinta"]


@pytest.mark.django_db
def test_las_pastillas_de_orden_conservan_los_filtros(client, admin_user, catalogo_surtido):
    client.force_login(admin_user)
    html = client.get("/catalogo/", {"q": "band", "orden": "precio"}).content.decode()
    assert "Ordenar por" in html
    assert "q=band&amp;orden=" in html, "la pastilla perdió la búsqueda"
    # La activa se ofrece invertida.
    assert "orden=-precio" in html


def test_las_pastillas_usan_el_estilo_canonico():
    assert "pill-filtro" in TPL_LISTA_CATALOGO.read_text(encoding="utf-8")


# ── 8 y 9. Fotos y medidas ───────────────────────────────────────────────────


def test_las_fichas_muestran_la_foto_completa():
    """«No mostrar imágenes recortadas al cuadrado sino completas, limitadas al
    alto actual del cuadrado» (Oscar)."""
    html = TPL_FICHAS.read_text(encoding="utf-8")
    assert "object-contain" in html
    assert "object-cover" not in html
    assert "h-16 w-auto" in html, "el alto es el que manda; el ancho se acomoda"


def test_la_tarjeta_de_producto_vuelve_a_las_medidas_del_render():
    texto = TPL_CARD.read_text(encoding="utf-8")
    # Fila 1: Categoría cede ancho; Cant./Merma/Precio quedan cómodos.
    # LC 2026-08-17: se intercaló una columna `auto` para el RADIO de la opción
    # (escalas de volumen) entre Producto y Cant. Los anchos de los campos son los
    # mismos; lo que cambió es que ahora hay 7 columnas y no 6.
    assert "md:grid-cols-[0.85fr_1.6fr_auto_minmax(96px,0.7fr)_minmax(96px,0.7fr)_minmax(104px,0.62fr)_40px]" in texto
    # Fila 2: Descripción es la ancha.
    assert "md:grid-cols-[1.35fr_minmax(104px,0.72fr)_2.95fr]" in texto
    # Fila 3: Impresión ocupa lo que ocupaba en el render.
    assert "md:grid-cols-[2.6fr_minmax(120px,0.68fr)_auto_auto]" in texto


def test_el_pie_de_la_tarjeta_usa_las_palabras_del_render():
    texto = TPL_CARD.read_text(encoding="utf-8")
    assert "Costo de producción:" in texto
    assert "Unitario <span" in texto
