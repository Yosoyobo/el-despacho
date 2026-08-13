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

from datetime import date
from decimal import Decimal
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


def test_deslizar_sobre_una_tarjeta_scrollea_la_pagina():
    """LC 2026-08-13 (Oscar): «no me deja scrollear a gusto por la página, agarra
    tareas y las arrastra». Con el dedo y sin asa hay que MANTENER PRESIONADO."""
    js = JS_ARRASTRE.read_text(encoding="utf-8")
    assert "ESPERA_TACTIL" in js, "no existe el «mantén presionado»"
    assert "setTimeout(agarrar, ESPERA_TACTIL)" in js
    # Mientras se espera NO se toca el gesto, así que la página se mueve.
    assert "sin `preventDefault`: la página se mueve" in js
    # Y si el dedo se mueve antes de tiempo, era scroll: se cancela.
    assert "cancelarEspera()" in js


def test_el_hover_no_se_queda_pegado_al_tocar():
    """LC 2026-08-13 (Oscar): «no me gusta el outline azul que se activa
    inmediatamente cuando mi dedo está encima de alguna».

    En táctil el navegador finge un `:hover` al tocar y lo deja pegado, así que
    el `hover:border-brand-300` de las tarjetas arrastrables pintaba el borde
    azul con sólo apoyar el dedo. Con este ajuste, Tailwind mete cada `hover:`
    dentro de `@media (hover: hover)`.
    """
    cfg = Path("el-taller/tailwind.config.js").read_text(encoding="utf-8")
    assert "hoverOnlyWhenSupported: true" in cfg
    # Y las tarjetas conservan su hover para quien sí tiene mouse.
    tarjeta = Path("el-taller/templates/pizarron/_kanban_tarjeta.html").read_text(encoding="utf-8")
    assert "hover:border-brand-300" in tarjeta


def test_solo_el_asa_bloquea_el_scroll():
    """El `touch-none` sobre TODA la tarjeta era la causa del bug: le decía al
    navegador «aquí no scrollees» en cada tarjeta del tablero."""
    js = JS_ARRASTRE.read_text(encoding="utf-8")
    assert "if (a) a.classList.add('touch-none');" in js
    # El scroll sólo se frena mientras se arrastra DE VERDAD, y desde touchmove
    # no pasivo (preventDefault en pointermove no lo garantiza).
    assert "{ passive: false }" in js
    assert "if (activo) e.preventDefault();" in js


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


# ── «Guardar te deja donde estás» ────────────────────────────────────────────


@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("/catalogo/?q=nike", "/catalogo/?q=nike"),   # ruta nuestra: se respeta
        ("//evil.com/x", "/fallback"),                # esquema relativo: fuera
        ("https://evil.com", "/fallback"),            # otro dominio: fuera
        ("/ok\nX-Malo: 1", "/fallback"),              # inyección de cabecera: fuera
        ("", "/fallback"),
        (None, "/fallback"),
    ],
)
def test_solo_se_regresa_a_rutas_nuestras(valor, esperado, rf):
    from lib.navegacion import destino_de_regreso

    peticion = rf.post("/x", {"volver": valor} if valor is not None else {})
    assert destino_de_regreso(peticion, "/fallback") == esperado


@pytest.fixture
def categoria():
    from apps.el_catalogo.models import CategoriaServicio
    return CategoriaServicio.objects.create(nombre="Textiles")


@pytest.fixture
def producto(categoria):
    from apps.el_catalogo.models import Servicio
    return Servicio.objects.create(
        nombre="Bandana Roja", categoria=categoria, precio_base=220, costo=44.94,
    )


@pytest.mark.django_db
def test_guardar_la_ficha_de_un_producto_te_deja_en_la_ficha(
    client, admin_user, producto, categoria,
):
    """La queja literal de Oscar: guardar lo sacaba a la lista."""
    client.force_login(admin_user)
    r = client.post(
        f"/catalogo/{producto.pk}/editar",
        {
            "nombre": "Bandana Roja", "categoria": categoria.pk,
            "precio_base": "230", "costo": "44.94", "unidad": "pz",
        },
    )
    assert r.status_code == 302
    assert r["Location"].startswith(f"/catalogo/{producto.pk}/editar"), r["Location"]
    producto.refresh_from_db()
    assert str(producto.precio_base) == "230.00", "además tenía que guardar"


@pytest.mark.django_db
def test_archivar_desde_la_lista_te_regresa_con_tus_filtros(client, admin_user, producto):
    client.force_login(admin_user)
    r = client.post(
        f"/catalogo/{producto.pk}/archivar",
        {"volver": "/catalogo/?q=bandana&editar=1"},
    )
    assert r.status_code == 302
    assert r["Location"] == "/catalogo/?q=bandana&editar=1"


@pytest.mark.django_db
def test_la_lista_de_productos_manda_de_donde_vienes(client, admin_user, producto):
    client.force_login(admin_user)
    # La tabla, que es donde viven el enlace de la fila y el form de archivar.
    html = client.get("/catalogo/", {"q": "bandana", "vista": "tabla"}).content.decode()
    assert "volver=" in html, "los enlaces de la fila no llevan de dónde vienes"
    assert 'name="volver"' in html, "el form de archivar no lleva de dónde vienes"


# ── La calculadora de Simil baja a los proyectos vivos ───────────────────────


@pytest.fixture
def simil(categoria):
    """Un producto de Simil Cuero Plymouth, que es quien usa la calculadora."""
    from apps.el_catalogo.calculadora import PROVEEDOR_CALCULADORA
    from apps.el_catalogo.models import Proveedor, Servicio

    prov = Proveedor.objects.create(razon_social=PROVEEDOR_CALCULADORA)
    srv = Servicio.objects.create(
        nombre="Mandil", categoria=categoria, precio_base=510, costo=Decimal("180.00"),
    )
    srv.proveedores.add(prov)
    return srv


def _linea(proyecto, servicio, **extra):
    from apps.los_proyectos.models import ProyectoProducto
    return ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=servicio, cantidad=10, **extra,
    )


@pytest.mark.django_db
def test_el_costo_nuevo_baja_a_los_proyectos_abiertos(cliente_nike, simil):
    from apps.el_catalogo.propagacion import propagar_costo
    from apps.los_proyectos.models import Proyecto

    p = Proyecto.objects.create(nombre="Vivo", cliente=cliente_nike, estado="en_proceso_diseno")
    linea = _linea(p, simil, costo_unitario=Decimal("180.00"))

    simil.costo = Decimal("210.00")
    simil.save(update_fields=["costo"])
    assert propagar_costo(simil, Decimal("180.00")) == 1

    linea.refresh_from_db()
    assert linea.costo_unitario == Decimal("210.00")


@pytest.mark.django_db
def test_una_linea_que_ya_genero_egreso_no_se_toca(cliente_nike, simil):
    """Ese dinero ya salió: moverlo hacia atrás descuadra la contabilidad."""
    from apps.el_catalogo.propagacion import propagar_costo
    from apps.los_proyectos.models import Proyecto
    from apps.tesoreria.models import CentroDeCosto, Egreso

    p = Proyecto.objects.create(nombre="En producción", cliente=cliente_nike,
                                estado="en_proceso_produccion")
    centro, _ = CentroDeCosto.objects.get_or_create(  # ya viene sembrado
        slug="insumos-de-proyecto", defaults={"nombre": "Insumos de proyecto"})
    egreso = Egreso.objects.create(monto=Decimal("1800.00"), descripcion="x",
                                   centro_de_costo=centro, fecha=date.today())
    linea = _linea(p, simil, costo_unitario=Decimal("180.00"), egreso=egreso)

    assert propagar_costo(simil, Decimal("180.00")) == 0
    linea.refresh_from_db()
    assert linea.costo_unitario == Decimal("180.00")


@pytest.mark.django_db
def test_un_proyecto_cerrado_o_archivado_no_se_toca(cliente_nike, simil):
    from apps.el_catalogo.propagacion import propagar_costo
    from apps.los_proyectos.models import Proyecto

    cerrado = Proyecto.objects.create(nombre="Cerrado", cliente=cliente_nike, estado="cerrado")
    archivado = Proyecto.objects.create(nombre="Archivado", cliente=cliente_nike,
                                        estado="en_proceso_diseno", archivado=True)
    l1 = _linea(cerrado, simil, costo_unitario=Decimal("180.00"))
    l2 = _linea(archivado, simil, costo_unitario=Decimal("180.00"))

    simil.costo = Decimal("210.00")
    assert propagar_costo(simil, Decimal("180.00")) == 0
    for linea in (l1, l2):
        linea.refresh_from_db()
        assert linea.costo_unitario == Decimal("180.00")


@pytest.mark.django_db
def test_un_costo_escrito_a_mano_se_respeta(cliente_nike, simil):
    """Un costo negociado para ese proyecto es una decisión, no una copia."""
    from apps.el_catalogo.propagacion import propagar_costo
    from apps.los_proyectos.models import Proyecto

    p = Proyecto.objects.create(nombre="Negociado", cliente=cliente_nike,
                                estado="en_proceso_diseno")
    linea = _linea(p, simil, costo_unitario=Decimal("150.00"))  # ≠ el del catálogo

    simil.costo = Decimal("210.00")
    assert propagar_costo(simil, Decimal("180.00")) == 0
    linea.refresh_from_db()
    assert linea.costo_unitario == Decimal("150.00")


@pytest.mark.django_db
def test_una_linea_sin_costo_propio_tambien_se_pone_al_dia(cliente_nike, simil):
    from apps.el_catalogo.propagacion import propagar_costo
    from apps.los_proyectos.models import Proyecto

    p = Proyecto.objects.create(nombre="Heredando", cliente=cliente_nike,
                                estado="en_proceso_diseno")
    linea = _linea(p, simil)  # costo_unitario = None ⇒ heredaba del catálogo

    simil.costo = Decimal("210.00")
    assert propagar_costo(simil, Decimal("180.00")) == 1
    linea.refresh_from_db()
    assert linea.costo_unitario == Decimal("210.00")


@pytest.mark.django_db
def test_guardar_la_calculadora_propaga_sin_tocar_lo_pagado(client, admin_user, cliente_nike, simil, categoria):
    """De punta a punta: se guarda la ficha y el proyecto abierto queda al día."""
    from apps.los_proyectos.models import Proyecto

    p = Proyecto.objects.create(nombre="Vivo", cliente=cliente_nike, estado="en_proceso_diseno")
    linea = _linea(p, simil, costo_unitario=Decimal("180.00"))
    client.force_login(admin_user)

    client.post(f"/catalogo/{simil.pk}/editar", {
        "nombre": "Mandil", "categoria": categoria.pk, "precio_base": "510",
        "costo": "180", "unidad": "pz",
        # El proveedor viaja en el POST: si no, el form limpia la M2M y el
        # producto deja de usar la calculadora.
        "proveedores": [p.pk for p in simil.proveedores.all()],
        "calc_material_0": "100", "calc_sublimacion_0": "20", "calc_mano_obra": "10",
    })
    simil.refresh_from_db()
    linea.refresh_from_db()
    assert simil.costo != Decimal("180.00"), "la calculadora tenía que recalcular"
    assert linea.costo_unitario == simil.costo


# ── La página de Productos abre en fichas ────────────────────────────────────


@pytest.mark.django_db
def test_productos_abre_en_fichas_y_la_tabla_queda_a_un_clic(client, admin_user, producto):
    client.force_login(admin_user)
    fichas = client.get("/catalogo/")
    assert fichas.context["en_tarjetas"] is True
    assert "☰ Ver en tabla" in fichas.content.decode()

    tabla = client.get("/catalogo/", {"vista": "tabla"})
    assert tabla.context["en_tarjetas"] is False
    assert "▦ Ver en fichas" in tabla.content.decode()


@pytest.mark.django_db
def test_la_edicion_rapida_sigue_siendo_la_tabla(client, admin_user, producto):
    client.force_login(admin_user)
    r = client.get("/catalogo/", {"editar": "1"})
    assert r.context["en_tarjetas"] is False
    assert r.context["editar_inline"] is True


@pytest.mark.django_db
def test_la_ficha_muestra_nombre_categoria_proveedor_y_numeros(client, admin_user, producto, categoria):
    from apps.el_catalogo.models import Proveedor

    prov = Proveedor.objects.create(razon_social="Crea Blanks")
    producto.proveedor_principal = prov
    producto.save(update_fields=["proveedor_principal"])
    producto.proveedores.add(prov)

    client.force_login(admin_user)
    html = client.get("/catalogo/").content.decode()
    assert "Bandana Roja" in html
    assert "Textiles" in html
    assert "Crea Blanks" in html
    assert "Margen" in html


@pytest.mark.django_db
def test_la_ficha_junta_la_foto_del_catalogo_y_las_de_sus_usos(cliente_nike, categoria):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    srv = Servicio.objects.create(nombre="Playera", categoria=categoria,
                                  precio_base=100, imagen_file_id="FOTO-CATALOGO")
    p = Proyecto.objects.create(nombre="Nike", cliente=cliente_nike)
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=1,
                                    imagen_file_id="FOTO-ALIAS")
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=1)  # sin foto

    assert srv.fotos_ficha == ["FOTO-CATALOGO", "FOTO-ALIAS"]


@pytest.mark.django_db
def test_las_fichas_no_hacen_una_consulta_por_producto(client, admin_user, categoria, cliente_nike):
    """El costo tiene que ser el mismo con 12 productos que con 24.

    La ficha de proveedores —de donde se copió el diseño— tiene un N+1 que hoy
    pasa desapercibido porque hay pocos proveedores. Con cientos de productos
    sería fatal, así que aquí queda la red.
    """
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    proyecto = Proyecto.objects.create(nombre="Nike", cliente=cliente_nike)

    def sembrar(desde, hasta):
        for i in range(desde, hasta):
            srv = Servicio.objects.create(nombre=f"Producto {i}", categoria=categoria,
                                          precio_base=100, imagen_file_id=f"F{i}")
            ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv,
                                            cantidad=1, imagen_file_id=f"U{i}")

    client.force_login(admin_user)
    sembrar(0, 12)
    with CaptureQueriesContext(connection) as con_12:
        assert client.get("/catalogo/").status_code == 200
    sembrar(12, 24)
    with CaptureQueriesContext(connection) as con_24:
        assert client.get("/catalogo/").status_code == 200

    assert len(con_24) == len(con_12), (
        f"el número de consultas crece con los productos: "
        f"{len(con_12)} con 12 y {len(con_24)} con 24 (N+1)"
    )


@pytest.mark.django_db
def test_el_proxy_guarda_lo_que_baja_y_no_vuelve_a_pedirselo_a_drive(client, admin_user, producto, monkeypatch):
    """Antes leía la caché pero nunca escribía: cada visita pegaba a Drive."""
    from django.core.cache import cache

    import lib.imagen_publica as imgpub

    cache.clear()
    producto.imagen_file_id = "FOTO-1"
    producto.save(update_fields=["imagen_file_id"])
    bajadas = []

    class DriveFalso:
        def descargar(self, file_id):
            bajadas.append(file_id)
            return b"\x89PNG-falso", "image/png", "foto.png"

    monkeypatch.setattr(imgpub, "_reducir", lambda c, m, lado=0: (c, m))
    monkeypatch.setitem(__import__("sys").modules, "lib.google_drive",
                        type("M", (), {"drive": DriveFalso()}))

    client.force_login(admin_user)
    for _ in range(3):
        r = client.get("/catalogo/imagen/FOTO-1", {"mini": "1"})
        assert r.status_code == 200
    assert len(bajadas) == 1, f"le pegó a Drive {len(bajadas)} veces en vez de una"
    assert "max-age=86400" in r["Cache-Control"]
    assert r["ETag"]


# ── El título del documento con un solo producto ─────────────────────────────


@pytest.mark.parametrize(
    "nombre,esperado",
    [
        ("Bandana Roja", "Bandanas Rojas"),
        ("Bandanas Rojas", "Bandanas Rojas"),      # ya venía en plural
        ("Gorra", "Gorras"),
        ("Lápiz", "Lápices"),
        ("Vinil", "Viniles"),
        ("Playera Dry Fit", "Playeras Dry Fit"),   # la marca no se toca
        ("Bandana Roja 'NIKE RUN'", "Bandanas Rojas 'NIKE RUN'"),
        ("Playera de Algodón", "Playeras de Algodón"),
        ("Libreta A5", "Libretas A5"),
        ("", ""),
    ],
)
def test_pluralizar(nombre, esperado):
    from lib.plural import pluralizar
    assert pluralizar(nombre) == esperado


@pytest.mark.django_db
def test_con_un_solo_producto_el_documento_se_titula_con_el_producto(cliente_nike, categoria):
    from apps.cotizaciones.models import Cotizacion
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="Nike Run 2026", cliente=cliente_nike)
    srv = Servicio.objects.create(nombre="Bandana Roja", categoria=categoria, precio_base=220)
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, cantidad=105)
    cot = Cotizacion.objects.create(cliente=cliente_nike, proyecto=proyecto, version=1)

    assert cot.titulo_documento == "Producción de Bandanas Rojas"


@pytest.mark.django_db
def test_con_varios_productos_vuelve_el_formato_de_siempre(cliente_nike, categoria):
    from apps.cotizaciones.models import Cotizacion
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="Nike Run 2026", cliente=cliente_nike)
    for nombre in ("Bandana Roja", "Gorra Negra"):
        srv = Servicio.objects.create(nombre=nombre, categoria=categoria, precio_base=100)
        ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, cantidad=10)
    cot = Cotizacion.objects.create(cliente=cliente_nike, proyecto=proyecto, version=1)

    assert cot.titulo_documento == "Producción de elementos para proyecto 'Nike Run 2026'"


# ── La tarjeta de producto ───────────────────────────────────────────────────

TPL_CARD = Path("el-taller/templates/proyectos/_producto_card.html")


def test_el_boton_dice_agregar_producto():
    for ruta in ("el-taller/templates/proyectos/detalle.html",
                 "el-taller/templates/proyectos/form.html"):
        texto = Path(ruta).read_text(encoding="utf-8")
        assert ">+ Agregar producto<" in texto, ruta
        assert ">+ Nuevo producto<" not in texto, ruta


def test_cantidad_y_merma_ya_no_se_encimam():
    """Los tracks eran fijos a 58px y la etiqueta CANTIDAD medía ~53."""
    texto = TPL_CARD.read_text(encoding="utf-8")
    assert "_58px_58px_" not in texto, "las columnas siguen sin poder crecer"
    assert "minmax(72px,auto)_minmax(72px,auto)" in texto
    assert ">Cant.<" in texto, "la etiqueta larga sigue ahí"


def test_los_campos_angostos_tienen_su_clase_en_las_dos_apps():
    from apps.los_proyectos.forms import ProyectoProductoForm

    form = ProyectoProductoForm()
    for campo in ("cantidad", "merma"):
        assert "campo-angosto" in form.fields[campo].widget.attrs.get("class", ""), campo
    taller = Path("el-taller/static/css/input.css").read_text(encoding="utf-8")
    gerencia = Path("la-gerencia/static/css/input.css").read_text(encoding="utf-8")
    assert ".campo-angosto" in taller and ".campo-angosto" in gerencia


# ── El costo unitario acepta cuentas ─────────────────────────────────────────


@pytest.mark.parametrize(
    "cuenta,total",
    [
        ("15.75*100", "1575.00"),
        ("2*3+4", "10.00"),          # la multiplicación va primero
        ("35+15+15", "65.00"),       # lo de antes sigue igual
        ("65", "65.00"),             # un número pelón también vale
        ("100-2*10", "80.00"),
        ("1.5*2*4", "12.00"),
    ],
)
def test_las_cuentas_del_costo(cuenta, total):
    from decimal import Decimal

    from apps.los_proyectos.services_procesos import suma_expresion
    assert suma_expresion(cuenta) == Decimal(total)


@pytest.mark.parametrize(
    "basura",
    ["35/2", "(2+3)*4", "abc", "35++15", "35*", "*15", "2**3", ".", ""],
)
def test_lo_que_no_es_una_cuenta_se_rechaza(basura):
    """La DIVISIÓN se sigue rechazando a propósito: con dos decimales pierde
    centavos (150 ÷ 29 × 29 = 149.93). Ése fue el error que ya nos costó."""
    from apps.los_proyectos.services_procesos import suma_expresion
    assert suma_expresion(basura) is None


def test_el_campo_del_costo_unitario_deja_teclear_la_cuenta():
    """Un `type=number` ni siquiera deja escribir el `*`."""
    from apps.los_proyectos.forms import ProyectoProductoForm

    widget = ProyectoProductoForm().fields["costo_unitario"].widget
    assert widget.input_type == "text"
    assert "costo-unit" in widget.attrs.get("class", "")
    assert "data-costo-suma" in TPL_CARD.read_text(encoding="utf-8")


@pytest.mark.django_db
def test_el_servidor_saca_el_total_y_conserva_la_cuenta_escrita(cliente_nike, categoria):
    from decimal import Decimal

    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.forms import ProyectoProductoForm
    from apps.los_proyectos.models import Proyecto

    proyecto = Proyecto.objects.create(nombre="Nike Run", cliente=cliente_nike)
    srv = Servicio.objects.create(nombre="Bandana", categoria=categoria, precio_base=220)
    form = ProyectoProductoForm(
        {"servicio": srv.pk, "cantidad": "10", "costo_unitario": "15.75*100", "merma": "0"},
    )
    assert form.is_valid(), form.errors
    linea = form.save(commit=False)
    linea.proyecto = proyecto
    linea.save()

    assert linea.costo_unitario == Decimal("1575.00")
    assert linea.costo_unitario_expr == "15.75*100", "la cuenta escrita se conserva"


@pytest.mark.django_db
def test_un_costo_ilegible_no_pasa(cliente_nike, categoria):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.forms import ProyectoProductoForm

    srv = Servicio.objects.create(nombre="Bandana", categoria=categoria, precio_base=220)
    form = ProyectoProductoForm(
        {"servicio": srv.pk, "cantidad": "10", "costo_unitario": "35/2", "merma": "0"},
    )
    assert not form.is_valid()
    assert "costo_unitario" in form.errors


@pytest.mark.django_db
def test_el_titulo_escrito_a_mano_sigue_mandando(cliente_nike, categoria):
    from apps.cotizaciones.models import Cotizacion
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto

    proyecto = Proyecto.objects.create(nombre="Nike Run 2026", cliente=cliente_nike)
    srv = Servicio.objects.create(nombre="Bandana Roja", categoria=categoria, precio_base=220)
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, cantidad=105)
    cot = Cotizacion.objects.create(
        cliente=cliente_nike, proyecto=proyecto, version=1,
        titulo_documento_manual="Lo que yo diga",
    )
    assert cot.titulo_documento == "Lo que yo diga"
