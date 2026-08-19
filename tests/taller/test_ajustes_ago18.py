"""Ronda de ajustes del 18 de agosto de 2026 (Oscar).

Diez puntos: la división en las cuentas, el orden de los campos de las opciones
de volumen, el título y el desglose que siguen a la opción activa, un color por
opción, los dos bugs de las tarjetas (se colapsan solas / la descripción se hace
grande y chica sola), colores de producto variados y ligados, las búsquedas sin
acentos, los toggles de IVA en gris y el documento (margen de arriba + el aire
entre la descripción y la tablita).
"""

from decimal import Decimal
from pathlib import Path

import pytest
from django.urls import reverse

RAIZ = Path(__file__).resolve().parent.parent.parent
TALLER = RAIZ / "el-taller"


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_user(
        email="jefa@lc.mx", password="x", rol="super_admin", nombre_completo="Jefa LC",
    )


@pytest.fixture
def cliente_nike():
    from apps.la_cartera.models import Cliente
    return Cliente.objects.create(razon_social="NIKE")


@pytest.fixture
def categoria():
    from apps.el_catalogo.models import CategoriaServicio
    return CategoriaServicio.objects.create(nombre="Textiles")


# ── 1. Las cuentas aceptan las cuatro operaciones ────────────────────────────

@pytest.mark.parametrize(("escrito", "esperado"), [
    ("150/29", "5.17"),          # el caso que se rechazaba a propósito
    ("2400/12", "200.00"),
    ("100/4*3", "75.00"),        # de izquierda a derecha, como siempre
    ("10-3/2", "8.50"),          # la división va antes que la resta
    ("150/29*29", "150.00"),     # se redondea UNA vez, al final
    ("35+15+15", "65.00"),
    ("15.75*100", "1575.00"),
    ("65", "65.00"),
])
def test_la_cuenta_acepta_division(escrito, esperado):
    from apps.los_proyectos.services_procesos import suma_expresion
    assert suma_expresion(escrito) == Decimal(esperado)


@pytest.mark.parametrize("basura", ["1/0", "35//2", "/5", "5/", "abc/2"])
def test_una_division_mal_escrita_no_se_interpreta(basura):
    """Entre cero no hay cuenta que valga, y una barra suelta tampoco."""
    from apps.los_proyectos.services_procesos import suma_expresion
    assert suma_expresion(basura) is None


@pytest.mark.django_db
def test_el_precio_unitario_acepta_cuenta_y_la_conserva_escrita(cliente_nike, categoria):
    """Oscar: «mantener el cálculo escrito, poner resultado en chiquito abajo»."""
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.forms import ProyectoProductoForm
    from apps.los_proyectos.models import Proyecto

    proyecto = Proyecto.objects.create(nombre="Cuentas", cliente=cliente_nike)
    srv = Servicio.objects.create(nombre="Playera", categoria=categoria, precio_base=100)
    form = ProyectoProductoForm({
        "servicio": srv.pk, "cantidad": "10", "merma": "0",
        "precio_unitario": "2400/12", "costo_unitario": "35+15",
        "incluir_en_calculo": "on",
    })
    assert form.is_valid(), form.errors
    linea = form.save(commit=False)
    linea.proyecto = proyecto
    linea.save()
    assert linea.precio_unitario == Decimal("200.00")
    assert linea.precio_unitario_expr == "2400/12"     # la cuenta se queda escrita
    assert linea.costo_unitario_expr == "35+15"


@pytest.mark.django_db
def test_un_precio_ilegible_no_pasa(cliente_nike, categoria):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.forms import ProyectoProductoForm

    srv = Servicio.objects.create(nombre="Bandana", categoria=categoria, precio_base=220)
    form = ProyectoProductoForm(
        {"servicio": srv.pk, "cantidad": "10", "precio_unitario": "1/0", "merma": "0"})
    assert not form.is_valid()
    assert "precio_unitario" in form.errors


def test_todos_los_campos_de_dinero_muestran_su_total_abajo():
    """El «= $65.00» en chiquito, en los campos que aceptan cuenta."""
    tarjeta = (TALLER / "templates/proyectos/_producto_card.html").read_text()
    for marca in ("data-precio-suma", "data-costo-suma", "data-imp-suma",
                  "data-proc-suma", "data-venta-suma"):
        assert marca in tarjeta, marca
    escala = (TALLER / "templates/proyectos/_escala_fila.html").read_text()
    assert "data-esc-costo-suma" in escala
    assert "data-esc-precio-suma" in escala
    js = (TALLER / "templates/proyectos/_form_productos_js.html").read_text()
    # El JS los pinta todos, no sólo los dos de antes.
    assert "data-venta-suma" in js and "data-esc-precio-suma" in js
    # …y su parser acepta la división, como el del servidor.
    assert "/[0-9.+\\-*/]+/" in js or "[0-9.+\\-*/]" in js


# ── 2. En la opción de volumen, el costo va antes que el precio ─────────────

def test_en_la_escala_el_costo_va_antes_que_el_precio():
    fila = (TALLER / "templates/proyectos/_escala_fila.html").read_text()
    assert fila.index("esc-costo") < fila.index("esc-precio")
    js = (TALLER / "templates/proyectos/_form_productos_js.html").read_text()
    plantilla = js[js.index("function plantillaEscala"):js.index("function agregarEscala")]
    assert plantilla.index("esc-costo") < plantilla.index("esc-precio")


def test_el_precio_de_la_escala_tambien_acepta_cuenta():
    fila = (TALLER / "templates/proyectos/_escala_fila.html").read_text()
    bloque = fila[fila.index("esc-precio") - 400:fila.index("esc-precio") + 200]
    assert 'type="text"' in bloque      # un input numérico ni deja teclear el «/»


# ── 3. El título de la tarjeta y el desglose siguen a la opción activa ──────

def test_el_titulo_de_la_tarjeta_habla_de_la_opcion_activa():
    js = (TALLER / "templates/proyectos/_form_productos_js.html").read_text()
    assert "function opcionActiva" in js
    resumen = js[js.index("const resumen = card.querySelector"):]
    assert "op.cant" in resumen and "op.precio" in resumen
    # Y cambiar de opción repinta el título de inmediato.
    assert "pintarSuma(card); serializarEscalas(card); recalcularEscalas(card); recalcular(card);" in js


@pytest.mark.django_db
def test_el_desglose_del_sidebar_usa_la_cantidad_de_la_opcion_activa(
        cliente_nike, categoria):
    """Decía «$175 x 70 pz» y cobraba 100: el precio ya era el de la escala
    activa pero la cantidad seguía siendo la de la Opción A."""
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import (
        Proyecto,
        ProyectoProducto,
        ProyectoProductoEscala,
    )

    proyecto = Proyecto.objects.create(nombre="Volumen", cliente=cliente_nike)
    srv = Servicio.objects.create(nombre="Playera", categoria=categoria, precio_base=195)
    linea = ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=srv, cantidad=70, precio_unitario=Decimal("195"))
    ProyectoProductoEscala.objects.create(
        producto=linea, orden=0, cantidad=100, precio_unitario=Decimal("175"), activa=True)

    linea.refresh_from_db()
    assert linea.cantidad_efectiva == 100
    assert linea.precio_efectivo == Decimal("175.00")
    assert linea.subtotal == Decimal("17500.00")

    panel = (TALLER / "templates/proyectos/_economico_panel.html").read_text()
    assert "pp.cantidad_efectiva" in panel
    assert "{{ pp.cantidad }}" not in panel


# ── 4. Cada opción de volumen, con su color ────────────────────────────────

def test_cada_opcion_de_volumen_tiene_su_color_empezando_por_el_azul():
    from apps.los_proyectos import colores
    from apps.los_proyectos.templatetags.proyectos_extras import color_escala

    assert color_escala(0) == colores.PALETA[0] == "#465fff"   # la B, el azul de la casa
    assert color_escala(1) != color_escala(0)
    assert color_escala(2) not in {color_escala(0), color_escala(1)}
    assert color_escala("basura") == colores.PALETA[0]         # nunca revienta


def test_la_fila_de_la_escala_lleva_su_color():
    fila = (TALLER / "templates/proyectos/_escala_fila.html").read_text()
    assert "--ec: {{ color_escala" in fila
    assert "escala-acento" in fila
    js = (TALLER / "templates/proyectos/_form_productos_js.html").read_text()
    # Al agregar o quitar una opción se vuelven a repartir letras Y colores.
    assert "PALETA_ESCALAS" in js
    assert "fila.style.setProperty('--ec'" in js


# ── 5. Las tarjetas ya no se colapsan solas ni se mueven de lugar ──────────

def test_el_acordeon_sobrevive_al_re_render_del_formset():
    """LC 2026-08-18 R2: el estado del acordeón vive en un REGISTRO que no se
    consume. La versión anterior lo anotaba en `htmx:beforeRequest` y lo reponía
    en `htmx:afterSettle`, con una variable que el primer `afterSettle` que
    llegara —el del polling del banner— se llevaba; ver
    `test_ajustes_ago18_r2.py`."""
    js = (TALLER / "templates/proyectos/_form_productos_js.html").read_text()
    assert "function anotarEstadoActual" in js and "function aplicarAcordeon" in js
    assert "htmx:afterSettle', aplicarAcordeon" in js
    # La tarjeta nueva (pk que el registro no conoce) nace abierta.
    assert "estadoAcordeon.has(pk) ? estadoAcordeon.get(pk) : true" in js


def test_la_tarjeta_nueva_nace_con_su_orden():
    """Nacía con `orden` 0 y al guardarse se colaba arriba de las demás."""
    js = (TALLER / "templates/proyectos/_form_productos_js.html").read_text()
    construir = js[js.index("function construirTarjeta"):js.index("const clonarUltima")]
    assert "__sincronizarOrdenProductos" in construir
    # Y al elegir el producto también, que es cuando la fila empieza a contar.
    prellenar = js[js.index("function prellenarServicio"):js.index("function aplicarProcesosDefault")]
    assert "__sincronizarOrdenProductos" in prellenar


# ── 6. La descripción ya no se hace grande y chica sola ───────────────────

def test_la_descripcion_no_se_mide_cuando_esta_escondida():
    """Medirla dentro de un `display:none` daba `scrollHeight` 0 y la aplastaba."""
    js = (TALLER / "templates/proyectos/_form_productos_js.html").read_text()
    autogrow = js[js.index("function autogrow(ta)"):js.index("window.__autogrowTarjeta")]
    assert "offsetParent === null" in autogrow
    # Y al desplegar la tarjeta se vuelve a medir.
    assert "window.__autogrowTarjeta" in js
    assert "__autogrowTarjeta(card)" in js


# ── 7. Colores de producto variados, contrastados y ligados ───────────────

def test_un_color_en_el_nombre_manda():
    from apps.los_proyectos import colores

    assert colores.color_del_texto("Playera dry fit negra") == "#1f2937"
    assert colores.color_del_texto("Bandana Roja") == colores.color_del_texto("ROJO")
    assert colores.color_del_texto("Azul marino") == "#1e3a8a"     # gana la combinación
    assert colores.color_del_texto("Gorra", "Color: verde limón") == "#65a30d"
    assert colores.color_del_texto("Playera") == ""                # sin color, sin regla


def test_no_confunde_un_color_con_un_pedazo_de_palabra():
    from apps.los_proyectos import colores
    assert colores.color_del_texto("Carroza alegórica") == ""      # «rosa» dentro de otra palabra
    assert colores.color_del_texto("Anegro") == ""


def test_la_lista_reparte_en_orden_y_sin_repetir():
    from apps.los_proyectos import colores

    assert colores.elegir_color_libre([]) == colores.PALETA[0]
    assert colores.elegir_color_libre([colores.PALETA[0]]) == colores.PALETA[1]
    assert colores.elegir_color_libre(colores.PALETA[:3]) == colores.PALETA[3]
    # Con la lista agotada se repite en vez de dejar la tarjeta sin identidad.
    assert colores.elegir_color_libre(colores.PALETA) in colores.PALETA
    assert len(set(colores.PALETA)) == len(colores.PALETA) == 20


@pytest.mark.django_db
def test_cada_producto_del_proyecto_estrena_color(cliente_nike, categoria):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="Colores", cliente=cliente_nike)
    lineas = []
    for i in range(4):
        srv = Servicio.objects.create(nombre=f"Producto {i}", categoria=categoria, precio_base=100)
        lineas.append(ProyectoProducto.objects.create(
            proyecto=proyecto, servicio=srv, cantidad=1))
    colores_usados = [linea.color for linea in lineas]
    assert len(set(colores_usados)) == 4                 # 100% variados
    assert colores_usados[0] == "#465fff"                # y en orden


@pytest.mark.django_db
def test_un_color_que_ya_dice_el_nombre_de_otra_linea_no_se_reparte(
        cliente_nike, categoria):
    """Si una línea ya se llama «Bandana roja», el rojo está tomado — aunque su
    columna `color` diga otra cosa."""
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos import colores
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="Sin choques", cliente=cliente_nike)
    roja = Servicio.objects.create(nombre="Bandana roja", categoria=categoria,
                                   precio_base=100)
    otra = Servicio.objects.create(nombre="Gorra", categoria=categoria,
                                   precio_base=100)
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=roja, cantidad=1)
    segunda = ProyectoProducto.objects.create(proyecto=proyecto, servicio=otra,
                                              cantidad=1)
    rojo = colores.color_del_texto("roja")
    assert segunda.color != rojo
    assert segunda.color_efectivo != rojo


@pytest.mark.django_db
def test_el_color_no_se_mueve_al_reordenar_ni_al_borrar(cliente_nike, categoria):
    """«Sólidamente ligados»: el color se guarda con la línea, no se recalcula."""
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="Estables", cliente=cliente_nike)
    srv_a = Servicio.objects.create(nombre="Uno", categoria=categoria, precio_base=100)
    srv_b = Servicio.objects.create(nombre="Dos", categoria=categoria, precio_base=100)
    a = ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv_a, cantidad=1)
    b = ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv_b, cantidad=1)
    color_b = b.color_efectivo

    a.delete()                       # se borra la primera
    b.orden = 5                      # y la otra se arrastra a otro lugar
    b.save()
    b.refresh_from_db()
    assert b.color_efectivo == color_b


@pytest.mark.django_db
def test_el_alias_con_color_pisa_al_color_repartido(cliente_nike, categoria):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="Alias", cliente=cliente_nike)
    srv = Servicio.objects.create(nombre="Playera", categoria=categoria, precio_base=100)
    linea = ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, cantidad=1)
    base = linea.color_efectivo
    linea.nombre_proyecto = "Playera Verde"
    linea.save()
    assert linea.color_efectivo == "#059669" != base
    # Y el color repartido sigue ahí, para cuando le quiten el color al nombre.
    assert linea.color_asignado == base


def test_nadie_le_pasa_a_la_tarjeta_un_token_en_vez_de_un_hex():
    """`--ec: brand` no es color: `color-mix` lo descarta y la tarjeta se queda
    sin fondo. Los cuatro sitios que arman una tarjeta deben mandar HEX."""
    import re
    for ruta in ("detalle.html", "form.html", "_formset_productos.html",
                 "_productos_version.html"):
        texto = (TALLER / "templates/proyectos" / ruta).read_text()
        for valor in re.findall(r'card_color="([^"]+)"', texto):
            assert valor.startswith("#"), f"{ruta}: card_color={valor}"


def test_la_tarjeta_se_pinta_con_el_hex_y_no_con_cinco_tokens():
    tarjeta = (TALLER / "templates/proyectos/_producto_card.html").read_text()
    assert "tarjeta-color" in tarjeta and "--ec: {{ card_color" in tarjeta
    assert "bg-blue-light-50" not in tarjeta        # los tokens viejos, fuera
    css = (TALLER / "static/css/input.css").read_text()
    assert ".tarjeta-color" in css and "color-mix" in css


# ── 8. Las búsquedas ignoran los acentos ─────────────────────────────────

@pytest.mark.parametrize(("busca", "guardado"), [
    ("numeros", "Números Rojos"),        # el caso que reportó Oscar
    ("Números", "Numeros rojos"),        # y al revés
    ("MUNECOS", "Muñecos de peluche"),
    ("bordon", "Bordón"),
])
@pytest.mark.django_db
def test_buscar_sin_acentos_encuentra_con_acentos(busca, guardado, cliente_nike):
    from apps.los_proyectos.models import Proyecto

    from lib.busqueda import q_texto

    Proyecto.objects.create(nombre=guardado, cliente=cliente_nike)
    assert Proyecto.objects.filter(q_texto(busca, "nombre")).count() == 1


@pytest.mark.django_db
def test_la_busqueda_sigue_descartando_lo_que_no_empata(cliente_nike):
    from apps.los_proyectos.models import Proyecto

    from lib.busqueda import q_texto

    Proyecto.objects.create(nombre="Números Rojos", cliente=cliente_nike)
    assert not Proyecto.objects.filter(q_texto("gorras", "nombre")).exists()


@pytest.mark.django_db
def test_un_texto_con_signos_no_rompe_la_consulta(cliente_nike):
    from apps.los_proyectos.models import Proyecto

    from lib.busqueda import q_texto

    Proyecto.objects.create(nombre="Diseño (3 colores) +IVA", cliente=cliente_nike)
    assert Proyecto.objects.filter(q_texto("(3 colores)", "nombre")).count() == 1
    assert Proyecto.objects.filter(q_texto("+IVA", "nombre")).count() == 1


def test_sin_texto_no_filtra_nada():
    from lib.busqueda import q_texto
    assert len(q_texto("", "nombre").children) == 0
    assert len(q_texto("hola").children) == 0


@pytest.mark.django_db
def test_el_buscador_del_dashboard_encuentra_sin_acentos(client, admin_user, cliente_nike):
    """Donde Oscar hizo la búsqueda que falló."""
    from apps.los_proyectos.models import Proyecto

    Proyecto.objects.create(nombre="Números Rojos", cliente=cliente_nike,
                            estado="entregado")
    client.force_login(admin_user)
    resp = client.get(reverse("taller-buscar-proyectos"), {"q": "numeros"})
    assert resp.status_code == 200
    assert b"meros Rojos" in resp.content


# ── 9. Los toggles de IVA, en gris ───────────────────────────────────────

def test_los_toggles_de_iva_del_panel_de_proveedores_van_en_gris():
    panel = (TALLER / "templates/proyectos/_proveedores_panel.html").read_text()
    bloque = panel[panel.index("proyectos-proveedor-iva"):panel.index("Monto:")]
    assert "bg-brand-500" not in bloque
    assert "text-brand-600" not in bloque
    assert "bg-gray-500" in bloque


# ── 10. El documento ─────────────────────────────────────────────────────

def test_el_documento_pide_tambien_el_margen_del_encabezado():
    """La pista de Oscar: el margen de arriba no se movía por el header."""
    from lib.google_drive import _peticiones_pagina

    peticiones = _peticiones_pagina({"margen_superior_pt": 36, "margen_pie_pt": 20,
                                     "margen_encabezado_pt": 12})
    estilo = peticiones[0]["updateDocumentStyle"]
    assert estilo["documentStyle"]["marginHeader"]["magnitude"] == 12.0
    assert "marginHeader" in estilo["fields"]
    assert estilo["documentStyle"]["useCustomHeaderFooterMargins"] is True


def test_la_pagina_del_documento_lleva_el_margen_del_encabezado():
    from apps.cotizaciones.services import PAGINA_DOCUMENTO
    assert PAGINA_DOCUMENTO["margen_encabezado_pt"] < PAGINA_DOCUMENTO["margen_superior_pt"]


def test_la_descripcion_y_la_foto_se_asientan_abajo():
    """Así el sobrante queda ARRIBA y la tablita pega con la descripción."""
    pdf = (TALLER / "templates/cotizaciones/pdf.html").read_text()
    bloque = pdf[pdf.index("{% for fila in filas %}"):pdf.index("Tabla de montos")]
    assert bloque.count("vertical-align:bottom") == 2      # el texto y la foto
    assert "vertical-align:middle" not in bloque


def test_la_foto_se_achico_un_poco():
    from apps.cotizaciones.services import _ALTO_FOTO_PT, _medida_foto

    assert _ALTO_FOTO_PT == 64
    ancho, alto = _medida_foto(2.0)          # una foto vertical 1×2
    assert alto == 64 and ancho == 32
    ancho, alto = _medida_foto(0.25)         # una apaisada 4×1
    assert ancho == 150 and alto == 38


def _plan(monkeypatch, libre_normal, libre_apretado):
    """Fija lo que «queda libre» en la hoja para probar la escalera."""
    from apps.cotizaciones import services

    def falso(cot, filas, items, *, apretado=False):
        return {"libre": libre_apretado if apretado else libre_normal}

    monkeypatch.setattr(services, "_paginar", falso)
    return services._plan_notas(object(), [], [], ["n1", "n2", "n3"])


def test_las_notas_caben_y_se_van_al_pie(monkeypatch):
    plan = _plan(monkeypatch, 400, 400)
    assert plan["apretado"] is False
    assert plan["espacio_pt"] > 0
    assert plan["brs"] == 0


def test_si_no_caben_se_aprieta_el_documento(monkeypatch):
    """«Apretar esa distancia a ver si lo arregla» — y muchas veces alcanza."""
    plan = _plan(monkeypatch, 100, 180)
    assert plan["apretado"] is True
    assert plan["espacio_pt"] > 0
    assert plan["brs"] == 0


def test_si_ni_apretando_caben_arrancan_a_dos_renglones(monkeypatch):
    plan = _plan(monkeypatch, 40, 60)
    assert plan["espacio_pt"] == 0
    assert plan["brs"] == 2


def test_el_modo_apretado_llega_al_documento():
    pdf = (TALLER / "templates/cotizaciones/pdf.html").read_text()
    assert "{% if apretado %}" in pdf
    assert "{% if brs_notas %}<br><br>{% endif %}" in pdf
