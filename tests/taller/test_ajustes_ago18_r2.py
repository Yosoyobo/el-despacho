"""Segunda ronda del 18 de agosto de 2026 (Oscar), sobre lo deployado ese día.

Cinco frentes: los colores de las tarjetas (que el alias mande sobre el nombre,
que haya variedad de verdad y que una tarjeta nueva estrene color), los dos bugs
que quedaron vivos (tarjetas en negro con outline blanco / tarjetas que se
cierran solas al elegir producto), la lista de proveedores con código de color,
el documento sin páginas en blanco, y el Kanban con el color en el contorno.
"""

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent.parent
TALLER = RAIZ / "el-taller"


@pytest.fixture
def cliente_lc():
    from apps.la_cartera.models import Cliente
    return Cliente.objects.create(razon_social="KARI KARI")


@pytest.fixture
def categoria():
    from apps.el_catalogo.models import CategoriaServicio
    return CategoriaServicio.objects.create(nombre="Textiles")


# ── 1. Quién gana cuando hay varios colores en juego ────────────────────────

def test_entre_textos_manda_el_orden_en_que_se_pasan():
    """El caso de LC-0044: «Números Azules» sobre un catálogo «Playera Roja».

    Antes los tres textos iban concatenados y se buscaba color por color en el
    orden de la LISTA, donde el rojo va antes que el azul — así que el alias no
    servía de nada.
    """
    from apps.los_proyectos import colores
    assert colores.color_del_texto("Números Azules", "Playera Roja", "") == "#465fff"
    # Y sin alias, manda el nombre del catálogo.
    assert colores.color_del_texto("", "Playera Roja", "") == "#e11d48"
    # Y sin ninguno de los dos, la descripción todavía puede decirlo.
    assert colores.color_del_texto("Mandil", "Delantal", "Color: verde") == "#059669"


@pytest.mark.parametrize(("texto", "esperado"), [
    ("Playera roja y azul", "#e11d48"),   # gana el que se menciona primero…
    ("Playera azul y roja", "#465fff"),   # …y sólo eso lo decide
])
def test_dentro_de_un_texto_gana_el_color_que_se_menciona_primero(texto, esperado):
    from apps.los_proyectos import colores
    assert colores.color_del_texto(texto) == esperado


def test_la_frase_larga_le_sigue_ganando_a_la_palabra_suelta():
    """«azul marino» empieza donde «azul», así que el desempate es el largo."""
    from apps.los_proyectos import colores
    assert colores.color_del_texto("Gorra azul marino") == "#1e3a8a"
    assert colores.color_del_texto("Camisa verde limón") == "#65a30d"


def test_el_amarillo_feo_ya_no_es_de_los_primeros_en_repartirse():
    """Oscar: «verde, rojo, amarillo (feo), rojo, rojo, azul». El ámbar `#f59e0b`
    era el cuarto de la lista, así que casi cualquier proyecto lo sacaba."""
    from apps.los_proyectos import colores
    assert "#f59e0b" not in colores.PALETA
    assert "#ca8a04" not in colores.PALETA[:6]     # el mostaza, a la segunda mitad
    assert len(set(colores.PALETA)) == len(colores.PALETA) == 20


@pytest.mark.django_db
def test_el_alias_azul_gana_al_catalogo_rojo(cliente_lc, categoria):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="LC-0044", cliente=cliente_lc)
    srv = Servicio.objects.create(nombre="Playera Roja", categoria=categoria,
                                  precio_base=100)
    linea = ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=srv, cantidad=1,
        nombre_proyecto="Números Azules",
        nota="Impresión sobre la playera roja de siempre")
    # El alias manda sobre el catálogo Y sobre la descripción, aunque las dos
    # digan «roja»: concatenados, el rojo ganaba por ir antes en la lista.
    assert linea.color_efectivo == "#465fff"


@pytest.mark.django_db
def test_una_linea_sin_color_en_el_alias_todavia_mira_el_catalogo(
        cliente_lc, categoria):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="Herencia", cliente=cliente_lc)
    # Una hermana primero, para que el azul NO sea además el color que le tocaba
    # por reparto: así el test mide la regla y no una coincidencia.
    otra = Servicio.objects.create(nombre="Tote", categoria=categoria, precio_base=100)
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=otra, cantidad=1)
    srv = Servicio.objects.create(nombre="Mandil azul", categoria=categoria,
                                  precio_base=100)
    linea = ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=srv, cantidad=1,
        nombre_proyecto="Mandil completo Kari Kari")
    assert linea.color_asignado != "#465fff"
    assert linea.color_efectivo == "#465fff"


@pytest.mark.django_db
def test_el_reparto_respeta_la_prioridad_nueva_al_ocupar_colores(
        cliente_lc, categoria):
    """Una hermana cuyo ALIAS dice «azul» ocupa el azul, aunque su producto de
    catálogo diga otra cosa."""
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="Ocupados", cliente=cliente_lc)
    srv_a = Servicio.objects.create(nombre="Playera Roja", categoria=categoria,
                                    precio_base=100)
    srv_b = Servicio.objects.create(nombre="Gorra", categoria=categoria,
                                    precio_base=100)
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv_a, cantidad=1,
                                    nombre_proyecto="Números Azules")
    otra = ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv_b,
                                           cantidad=1)
    assert otra.color != "#465fff"      # el azul está tomado por el alias


# ── 2. Proyectos EXISTENTES: la migración vuelve a repartir ─────────────────

@pytest.mark.django_db
def test_la_migracion_recolorea_lo_que_ya_existe(cliente_lc, categoria):
    """Oscar: «quiero ver en proyectos nuevos **y existentes** algo variado».

    Se le pasa el registro REAL de modelos a la data migration — corre igual
    porque no usa properties (patrón de S-Ajustes-Ago12-B).
    """
    import importlib

    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto
    from django.apps import apps as registro

    # El módulo empieza con dígito: no se puede importar con `from … import`.
    migracion = importlib.import_module(
        "apps.los_proyectos.migrations.0037_recolorear_tarjetas")

    proyecto = Proyecto.objects.create(nombre="Viejito", cliente=cliente_lc)
    lineas = []
    for i in range(4):
        srv = Servicio.objects.create(nombre=f"Cosa {i}", categoria=categoria,
                                      precio_base=100)
        lineas.append(ProyectoProducto.objects.create(
            proyecto=proyecto, servicio=srv, cantidad=1, orden=i))
    # Se ensucian a mano, como si vinieran del reparto viejo.
    ProyectoProducto.objects.filter(proyecto=proyecto).update(color="#f59e0b")

    migracion._recolorear(registro, None)

    frescos = [linea.color for linea in
               ProyectoProducto.objects.filter(proyecto=proyecto).order_by("orden")]
    assert len(set(frescos)) == 4                 # variados otra vez
    assert "#f59e0b" not in frescos               # y sin el ámbar retirado


# ── 3. La tarjeta nueva estrena color (y no siempre el mismo) ──────────────

def test_la_tarjeta_nueva_recibe_un_color_libre_del_tablero():
    js = (TALLER / "templates/proyectos/_form_productos_js.html").read_text()
    assert "function colorLibreEnTablero" in js
    assert "function repartirColorNuevo" in js
    construir = js[js.index("function construirTarjeta"):js.index("const clonarUltima")]
    assert "repartirColorNuevo(card)" in construir


def test_el_color_elegido_en_el_front_viaja_al_servidor():
    """Sin el hidden, el color que se vio al capturar y el que se guarda podrían
    no coincidir."""
    from apps.los_proyectos.forms import ProyectoProductoForm
    assert "color" in ProyectoProductoForm.Meta.fields
    tarjeta = (TALLER / "templates/proyectos/_producto_card.html").read_text()
    assert "{{ f.color }}" in tarjeta


@pytest.mark.django_db
def test_un_color_vacio_no_le_cambia_el_color_a_una_linea_guardada(
        cliente_lc, categoria):
    """Vaciarlo haría que el `save()` del modelo repartiera otro y la tarjeta
    cambiaría sola en el siguiente autoguardado."""
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.forms import ProyectoProductoForm
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="Estable", cliente=cliente_lc)
    srv = Servicio.objects.create(nombre="Gorra", categoria=categoria, precio_base=100)
    linea = ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, cantidad=1)
    previo = linea.color

    form = ProyectoProductoForm(
        {"servicio": srv.pk, "cantidad": "1", "merma": "0", "orden": "0",
         "color": ""},
        instance=linea)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["color"] == previo


@pytest.mark.django_db
def test_un_color_inventado_no_entra(cliente_lc, categoria):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.forms import ProyectoProductoForm
    from apps.los_proyectos.models import Proyecto

    proyecto = Proyecto.objects.create(nombre="Basura", cliente=cliente_lc)
    srv = Servicio.objects.create(nombre="Gorra", categoria=categoria, precio_base=100)
    form = ProyectoProductoForm(
        {"servicio": srv.pk, "cantidad": "1", "merma": "0", "orden": "0",
         "color": "brand-500"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["color"] == ""     # y el modelo reparte al guardar
    assert proyecto.pk


# ── 4. El bug de las tarjetas en negro con outline blanco ──────────────────

def test_el_color_de_la_tarjeta_no_depende_del_css_compilado():
    """Con el color sólo en `.tarjeta-color`, cualquier momento en que esa hoja
    no esté deja la tarjeta sin fondo (negra en oscuro) y con el borde en
    `currentColor` (blanco) — lo que reportó Oscar."""
    tarjeta = (TALLER / "templates/proyectos/_producto_card.html").read_text()
    assert "background-color: color-mix(in srgb, var(--ec)" in tarjeta
    assert "border-color: color-mix(in srgb, var(--ec)" in tarjeta
    # Y sigue apoyándose en la variable, para que el JS repinte cambiando una sola.
    assert "--ec: {{ card_color" in tarjeta


def test_la_clase_de_la_tarjeta_usa_alpha_y_sirve_en_los_dos_temas():
    css = (TALLER / "static/css/input.css").read_text()
    bloque = css[css.index(".tarjeta-color {"):css.index(".escala-acento")]
    assert "transparent" in bloque and "#ffffff" not in bloque
    assert ".dark .tarjeta-color" not in css     # un solo par de valores


def test_la_tarjeta_apagada_se_sigue_viendo_apagada():
    """Con el fondo inline, un `bg-gray-100` de utility ya no puede pisarlo — y
    tampoco hace falta: el `grayscale` desatura el fondo del color."""
    js = (TALLER / "templates/proyectos/_form_productos_js.html").read_text()
    assert "card.classList.toggle('grayscale', !incluido)" in js
    assert "card.classList.toggle('bg-gray-100'" not in js
    assert "card.classList.toggle('dark:bg-white/[0.03]'" not in js


# ── 5. Las tarjetas ya no se cierran solas al elegir producto ──────────────

def test_el_estado_del_acordeon_no_se_lo_puede_llevar_otro_request():
    """La versión anterior anotaba en `beforeRequest` y reponía en
    `afterSettle`, con UNA variable que el `afterSettle` consumía. En esta
    página pollean el banner de deploy y el semáforo cada 10s, así que
    cualquiera de ellos se llevaba la anotación antes de que llegara el swap del
    formset."""
    js = (TALLER / "templates/proyectos/_form_productos_js.html").read_text()
    assert "acordeonPrevio" not in js
    assert "htmx:beforeRequest', anotarAcordeon" not in js
    assert "const estadoAcordeon = new Map()" in js
    # El registro se alimenta de lo que el usuario decide, no de un snapshot.
    assert "__anotarAcordeonProductos" in js


# ── 6. La lista de proveedores, con código de color ───────────────────────

def test_cada_proveedor_tiene_su_color_estable():
    from apps.los_proyectos import colores
    from apps.los_proyectos.templatetags.proyectos_extras import color_nombre

    assert color_nombre("Simil Cuero Plymouth") == color_nombre("Simil Cuero Plymouth")
    assert color_nombre("Simil Cuero Plymouth") != color_nombre("Crea Blanks")
    assert color_nombre("Crea Blanks") in colores.PALETA


def test_el_panel_de_proveedores_pinta_el_nombre():
    panel = (TALLER / "templates/proyectos/_proveedores_panel.html").read_text()
    assert "texto-color" in panel and "color_nombre" in panel
    css = (TALLER / "static/css/input.css").read_text()
    assert ".texto-color" in css and ".dark .texto-color" in css


# ── 7. El Kanban: el color al contorno, y los nombres más grandes ──────────

def _sin_comentarios(texto: str) -> str:
    """El HTML sin los bloques `{% comment %}`: los comentarios de este sprint
    citan las clases viejas para explicar cómo revertir."""
    import re
    return re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "",
                  texto, flags=re.S)


def test_el_kanban_pinta_el_color_en_el_contorno_de_la_pastilla():
    col = _sin_comentarios(
        (TALLER / "templates/proyectos/_kanban_columna.html").read_text())
    tarjeta = col[col.index("data-arr-item"):col.index("kanban-card") + 300]
    assert "border-color: {{ p.estado|color_estado }}" in tarjeta
    assert "border-left-color:" not in tarjeta
    assert "border-l-4" not in tarjeta
    # El hover ya no puede pisar el color del estado.
    assert "hover:border-brand-300" not in tarjeta


def test_el_kanban_muestra_proyecto_y_cliente_mas_grandes():
    col = (TALLER / "templates/proyectos/_kanban_columna.html").read_text()
    assert 'class="line-clamp-2 text-sm font-semibold' in col
    assert 'class="truncate text-xs text-gray-500' in col


# ── 8. El documento: sin páginas en blanco ─────────────────────────────────

def test_el_estimador_cuenta_el_margen_de_arriba_que_google_aplica():
    """Oscar: «lo del margen superior no funcionó». Si el estimador contara el
    que se PIDE, creería que hay 36pt más de hoja de los que hay."""
    from apps.cotizaciones import services

    assert services._ALTO_UTIL_PT == 792 - 72 - services._MARGEN_INFERIOR_PT
    # Se le sigue pidiendo el chico: no cuesta nada y si algún día lo respeta,
    # sólo sobra aire.
    assert services.PAGINA_DOCUMENTO["margen_superior_pt"] == 36


def test_la_paginacion_reserva_la_cola_del_documento():
    """Google cierra el cuerpo con un párrafo propio; si el contenido termina
    pegado al borde, ese párrafo se va solo a una hoja nueva."""
    from apps.cotizaciones import services

    class _Cot:
        incluir_desglose = False

        def calcular_totales(self):
            return {"impuestos_detalle": []}

    libre = services._paginar(_Cot(), [], [])["libre"]
    assert libre == (services._ALTO_UTIL_PT - services._ALTO_ENCABEZADO_PT
                     - services._COLA_DOCUMENTO_PT)


class _CotSinDesglose:
    incluir_desglose = False
    terminos = ""

    def calcular_totales(self):
        return {"impuestos_detalle": []}


def _plan_con_libre(monkeypatch, libre_pt, notas):
    """La escalera de `_plan_notas` con un espacio libre CONTROLADO.

    Se sustituye `_paginar` en vez de armar una cotización que ocupe justo lo
    necesario: el estimador reparte por bloques atómicos, así que no hay forma de
    pedirle un sobrante exacto y el caso interesante —«cabe, pero justo»— es una
    franja de 56pt.
    """
    from apps.cotizaciones import services
    monkeypatch.setattr(services, "_paginar",
                        lambda *a, **k: {"libre": libre_pt})
    return services._plan_notas(_CotSinDesglose(), [], [], notas)


def _alto_de(notas) -> int:
    return 18 + len(notas) * 13


def test_con_lugar_de_sobra_las_notas_se_van_al_pie(monkeypatch):
    """Escalón 1, el de siempre: hueco dinámico con tope."""
    from apps.cotizaciones import services
    notas = ["nota"] * 8
    plan = _plan_con_libre(monkeypatch, _alto_de(notas) + 400, notas)
    assert plan["brs"] == 0
    assert 0 < plan["espacio_pt"] <= services._TOPE_HUECO_NOTAS_PT


def test_si_las_notas_caben_justas_se_quedan_en_la_hoja_sin_aire(monkeypatch):
    """Escalón 3 — «puedes quitar los <br>s entre el último elemento y el bloque
    de notas para que quepa todo». Es lo que evita la hoja de más: antes, entre
    «cabe» y «cabe con holgura» se mandaba una hoja entera a la basura."""
    notas = ["nota"] * 8
    plan = _plan_con_libre(monkeypatch, _alto_de(notas) + 20, notas)
    assert plan["brs"] == 0, "no debe mandar una hoja entera a la basura"
    assert plan["espacio_pt"] == 0
    assert plan["apretado"] is True


def test_si_de_plano_no_caben_pasan_enteras_a_la_hoja_siguiente(monkeypatch):
    """Escalón 4: el bloque viaja en una fila con `preventOverflow`, así que no
    se parte — arranca la hoja siguiente con dos renglones de aire."""
    notas = ["nota"] * 8
    plan = _plan_con_libre(monkeypatch, _alto_de(notas) - 30, notas)
    assert plan["brs"] == 2 and plan["espacio_pt"] == 0


def test_si_no_se_puede_blindar_la_paginacion_queda_aviso(caplog):
    """Era un `except` mudo. Si algún día vuelve a partirse un bloque, lo primero
    que hay que saber es si la protección llegó a aplicarse."""
    import logging

    from lib.google_drive import GoogleDriveWrapper

    wrapper = object.__new__(GoogleDriveWrapper)
    wrapper._headers = lambda: (_ for _ in ()).throw(RuntimeError("sin token"))
    with caplog.at_level(logging.WARNING, logger="lib.google_drive"):
        assert wrapper._endurecer_paginacion("doc-123") is False
    assert "paginación" in caplog.text and "doc-123" in caplog.text


def test_el_hueco_de_las_notas_nunca_pasa_del_tope():
    from apps.cotizaciones import services
    assert services._TOPE_HUECO_NOTAS_PT == 96
    assert services._COLA_DOCUMENTO_PT > 0
