"""LC 2026-08-04 (tercera ronda) — ajustes de Oscar sobre el deploy del día.

Cubre el ticket completo:

* Tarjeta de producto: color FIJO por producto, el toggle ya no reordena, sigue
  visible con la tarjeta colapsada, y el «⧉» duplica la línea con sus procesos.
* Costo de Impresión que acepta una cuenta escrita («35+15+15» = 65) y la
  conserva tal cual.
* El proveedor que se le pone a una línea se liga al catálogo sin moverle el
  principal.
* Kanban: arrastrar para reordenar dentro de la columna (orden compartido).
* «Próximos eventos» del Dashboard: sólo compromisos de diseño en adelante, y
  sin el texto «Compromiso».
* Guardar flotante, buscador del Dashboard, botones del Chalán en gris,
  tabita de crear producto, ingresos/egresos y comentarios compactos, y la
  versión visible en la página de la cotización.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

TPL_CARD = Path("el-taller/templates/proyectos/_producto_card.html")
TPL_JS = Path("el-taller/templates/proyectos/_form_productos_js.html")
TPL_DETALLE = Path("el-taller/templates/proyectos/detalle.html")


# ── Fixtures mínimos ─────────────────────────────────────────────────────────


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_user(
        email="jefa@lc.mx", password="x", rol="super_admin", nombre_completo="Jefa LC",
    )


@pytest.fixture
def catalogo():
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    cat = CategoriaServicio.objects.create(nombre="Maquila")
    srv = Servicio.objects.create(
        nombre="Playera dry fit", categoria=cat,
        costo=Decimal("44.94"), precio_base=Decimal("190.00"),
    )
    prov_a = Proveedor.objects.create(razon_social="Zeta Textiles")
    prov_b = Proveedor.objects.create(razon_social="Alfa Bordados")
    srv.proveedores.add(prov_a)
    srv.proveedor_principal = prov_a
    srv.save(update_fields=["proveedor_principal"])
    return {"cat": cat, "srv": srv, "prov_a": prov_a, "prov_b": prov_b}


@pytest.fixture
def proyecto(catalogo):
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto
    cli = Cliente.objects.create(razon_social="Corriendo Club")
    return Proyecto.objects.create(nombre="Playeras Corriendo Club", cliente=cli)


# ── (1) Cuentas en el costo de Impresión: «35+15+15» ─────────────────────────


@pytest.mark.parametrize(("escrito", "esperado"), [
    ("35+15+15", "65.00"),
    ("35 + 15 + 15", "65.00"),
    ("100-5", "95.00"),
    ("65", "65.00"),
    ("65.50", "65.50"),
    # LC 2026-08-12: se sumó la multiplicación. La división NO — con dos
    # decimales pierde centavos, que es el error que ya nos costó una vez.
    ("15.75*100", "1575.00"),
    ("35*2", "70.00"),
])
def test_la_cuenta_del_costo_se_suma(escrito, esperado):
    from apps.los_proyectos.services_procesos import suma_expresion
    assert suma_expresion(escrito) == Decimal(esperado)


@pytest.mark.parametrize("basura", ["35++15", "35+", "abc", "", "35/2", "."])
def test_una_cuenta_mal_escrita_no_se_interpreta(basura):
    from apps.los_proyectos.services_procesos import suma_expresion
    assert suma_expresion(basura) is None


def test_la_cuenta_se_guarda_escrita_y_el_total_lo_saca_el_servidor(proyecto, catalogo):
    """El total NO se toma del front: se recalcula de la cuenta escrita."""
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.services_procesos import sincronizar_procesos
    linea = ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=catalogo["srv"], cantidad=29,
    )
    # El front manda un total equivocado a propósito: manda la cuenta.
    sincronizar_procesos(linea, (
        f'[{{"tipo": "impresion", "proveedor_id": {catalogo["prov_a"].pk},'
        f' "costo": 999, "costo_expr": "35+15+15", "por_pieza": true}}]'
    ))
    proc = linea.procesos.get()
    assert proc.costo_expr == "35+15+15"
    assert proc.costo == Decimal("65.00")


def test_un_numero_pelon_no_guarda_cuenta(proyecto, catalogo):
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.services_procesos import sincronizar_procesos
    linea = ProyectoProducto.objects.create(proyecto=proyecto, servicio=catalogo["srv"])
    sincronizar_procesos(linea, (
        f'[{{"tipo": "impresion", "proveedor_id": {catalogo["prov_a"].pk},'
        f' "costo": "39.00", "costo_expr": "39.00", "por_pieza": true}}]'
    ))
    proc = linea.procesos.get()
    assert proc.costo_expr == ""  # no es una cuenta, es un número
    assert proc.costo == Decimal("39.00")


def test_el_campo_de_impresion_acepta_texto_y_muestra_el_total():
    tpl = TPL_CARD.read_text(encoding="utf-8")
    ini = tpl.index('class="imp-costo')
    campo = tpl[tpl.rindex("<input", 0, ini):tpl.index(">", ini) + 1]
    # Un input numérico ni deja teclear el «+».
    assert 'type="text"' in campo
    assert "35+15+15" in campo  # el placeholder lo enseña
    assert "data-imp-suma" in tpl  # el «= $65.00» al lado
    js = TPL_JS.read_text(encoding="utf-8")
    assert "function evalSuma" in js and "numCuenta" in js
    assert "eval(" not in js  # nunca se evalúa texto del usuario


# ── (2) El caso de las Playeras: 2,584.26 es lo correcto ─────────────────────


def test_el_costo_de_produccion_de_las_playeras_no_pierde_centavos(proyecto, catalogo):
    """Reporte de Oscar: el sistema dio 2,584.26 y su cuenta a mano 2,584.19.

    El sistema tiene razón: los $150 de «adaptación y positivos» son un monto
    FIJO y entran completos. Los 7 centavos de diferencia salen de repartirlos a
    mano (150 ÷ 29 = 5.1724 → 5.17 × 29 = 149.93). Este test fija las dos cosas:
    el total correcto y de dónde venía la diferencia.
    """
    from apps.los_proyectos.models import ProyectoProducto, ProyectoProductoProceso
    linea = ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=catalogo["srv"], cantidad=29, merma=0,
        costo_unitario=Decimal("44.94"), precio_unitario=Decimal("190.00"),
    )
    ProyectoProductoProceso.objects.create(
        producto=linea, tipo="impresion", proveedor=catalogo["prov_a"],
        costo=Decimal("39.00"), por_pieza=True,
    )
    ProyectoProductoProceso.objects.create(
        producto=linea, tipo="operativo", descripcion="Adaptación y positivos",
        costo=Decimal("150.00"), por_pieza=False,
    )
    assert linea.costo_total_con_procesos == Decimal("2584.26")
    # La forma redondeada de repartir el monto fijo es la que pierde centavos.
    por_pieza_redondeado = (Decimal("150") / 29).quantize(Decimal("0.01"))
    a_mano = Decimal("44.94") * 29 + Decimal("39") * 29 + por_pieza_redondeado * 29
    assert a_mano == Decimal("2584.19")
    # Invariante: el costo por pieza × piezas producidas reconstruye el total.
    assert linea.costo_unitario_real * 29 == linea.costo_total_con_procesos


# ── (3) Tarjeta: color fijo, toggle que no mueve, y Duplicar ─────────────────


def test_el_color_de_la_tarjeta_es_estable_por_producto():
    from apps.los_proyectos.templatetags.proyectos_extras import color_tarjeta
    assert color_tarjeta(7) == color_tarjeta(7)  # mismo producto → mismo color
    assert color_tarjeta(None) == "brand"        # línea sin guardar
    assert color_tarjeta("") == "brand"
    # Y ya no se rota por posición con {% cycle %}.
    formset = Path("el-taller/templates/proyectos/_formset_productos.html").read_text(encoding="utf-8")
    assert "{% cycle" not in formset
    assert "color_tarjeta" in formset


def test_el_toggle_ya_no_reacomoda_las_tarjetas():
    from apps.los_proyectos.models import ProyectoProducto
    # El ordering del modelo ya no manda las incluidas al tope.
    assert ProyectoProducto._meta.ordering == ["orden", "creado_en"]
    js = TPL_JS.read_text(encoding="utf-8")
    # Ni el JS las sube/baja al prender o apagar el toggle.
    assert "insertBefore(card, primera)" not in js


def test_el_toggle_se_ve_con_la_tarjeta_colapsada():
    tpl = TPL_CARD.read_text(encoding="utf-8")
    barra = tpl[tpl.index("<div data-card-barra"):tpl.index("<div data-card-body")]
    assert "incluir_en_calculo" in barra, "el toggle debe vivir en la cabecera"
    js = TPL_JS.read_text(encoding="utf-8")
    # Picar el toggle apaga la línea; NO despliega la tarjeta.
    assert "[data-drag-handle], [data-img-slot], label, input" in js


def test_duplicar_clona_la_linea_con_sus_procesos(client, admin_user, proyecto, catalogo):
    from apps.los_proyectos.models import (
        ProyectoProducto,
        ProyectoProductoProceso,
        ProyectoProductoVenta,
    )
    linea = ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=catalogo["srv"], cantidad=29, merma=2,
        nombre_proyecto="Playera Janet", nota="Color beige",
        proveedor=catalogo["prov_a"], orden=0,
    )
    ProyectoProductoProceso.objects.create(
        producto=linea, tipo="impresion", proveedor=catalogo["prov_a"],
        costo=Decimal("65.00"), costo_expr="35+15+15", por_pieza=True,
    )
    ProyectoProductoVenta.objects.create(
        producto=linea, descripcion="Ponchado", cantidad=1,
        precio_unitario=Decimal("300.00"),
    )
    # Una segunda línea después, para comprobar que se hace hueco.
    otra = ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=catalogo["srv"], cantidad=1, orden=1,
    )
    client.force_login(admin_user)
    resp = client.post(f"/proyectos/{proyecto.pk}/duplicar-producto/{linea.pk}")
    assert resp.status_code in (204, 302)

    copia = ProyectoProducto.objects.exclude(pk__in=[linea.pk, otra.pk]).get()
    assert copia.nombre_proyecto == "Playera Janet"
    assert copia.cantidad == 29 and copia.merma == 2
    assert copia.nota == "Color beige"
    assert copia.proveedor_id == catalogo["prov_a"].pk
    assert copia.orden == 1  # justo debajo de la original
    otra.refresh_from_db()
    assert otra.orden == 2  # se corrió para dejarle el lugar
    proc = copia.procesos.get()
    assert proc.costo_expr == "35+15+15" and proc.costo == Decimal("65.00")
    assert copia.ventas.get().descripcion == "Ponchado"
    # El egreso NO se hereda: es de la línea original.
    assert copia.egreso_id is None


def test_el_boton_duplicar_solo_sale_donde_hay_autoguardado():
    tpl = TPL_CARD.read_text(encoding="utf-8")
    assert "f.instance.pk and con_autosave" in tpl
    detalle = TPL_DETALLE.read_text(encoding="utf-8")
    assert 'with con_autosave=True' in detalle


# ── (4) El proveedor de la línea se liga al catálogo ────────────────────────


def test_el_proveedor_de_la_linea_se_liga_sin_mover_al_principal(proyecto, catalogo):
    from apps.los_proyectos.models import ProyectoProducto
    srv, prov_a, prov_b = catalogo["srv"], catalogo["prov_a"], catalogo["prov_b"]
    # «Alfa» va antes que «Zeta» alfabéticamente: con la lógica vieja le habría
    # robado el default al principal de siempre.
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, proveedor=prov_b)
    srv.refresh_from_db()
    assert prov_b in srv.proveedores.all()      # quedó ligado (fuerte)
    assert srv.proveedor_principal_id == prov_a.pk  # el principal no se movió
    assert srv.proveedor_default == prov_a


def test_si_el_producto_no_tenia_principal_lo_toma_del_proyecto(proyecto, catalogo):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    huerfano = Servicio.objects.create(
        nombre="Termo acero",
        categoria=CategoriaServicio.objects.first() or CategoriaServicio.objects.create(nombre="Otros"),
        precio_base=Decimal("410.00"),
    )
    assert huerfano.proveedor_principal_id is None
    ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=huerfano, proveedor=catalogo["prov_b"],
    )
    huerfano.refresh_from_db()
    assert huerfano.proveedor_principal_id == catalogo["prov_b"].pk


def test_una_linea_sin_proveedor_no_toca_el_catalogo(proyecto, catalogo):
    from apps.los_proyectos.models import ProyectoProducto
    srv = catalogo["srv"]
    antes = set(srv.proveedores.values_list("pk", flat=True))
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, proveedor=None)
    srv.refresh_from_db()
    assert set(srv.proveedores.values_list("pk", flat=True)) == antes


# ── (5) Kanban: arrastrar para reordenar ────────────────────────────────────


def test_reordenar_el_kanban_guarda_el_orden(client, admin_user, catalogo):
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto
    cli = Cliente.objects.create(razon_social="Kari Kari")
    a = Proyecto.objects.create(nombre="Uno", cliente=cli, estado="en_proceso_diseno")
    b = Proyecto.objects.create(nombre="Dos", cliente=cli, estado="en_proceso_diseno")
    client.force_login(admin_user)
    resp = client.post("/proyectos/reordenar-kanban", {"orden": [str(b.pk), str(a.pk)]})
    assert resp.status_code == 204
    a.refresh_from_db()
    b.refresh_from_db()
    assert (b.orden_kanban, a.orden_kanban) == (0, 1)


def test_el_kanban_respeta_el_orden_guardado(client, admin_user):
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto
    cli = Cliente.objects.create(razon_social="Kari Kari")
    primero = Proyecto.objects.create(nombre="Debe salir primero", cliente=cli,
                                      estado="en_proceso_diseno", orden_kanban=0)
    segundo = Proyecto.objects.create(nombre="Debe salir segundo", cliente=cli,
                                      estado="en_proceso_diseno", orden_kanban=1)
    client.force_login(admin_user)
    html = client.get("/proyectos/kanban/").content.decode()
    assert html.index(primero.nombre) < html.index(segundo.nombre)


def test_el_arrastre_del_kanban_persiste_por_su_endpoint():
    # LC 2026-08-12: el gesto se unificó en El Arrastre
    # (static/js/arrastrar.js); la columna declara su endpoint por atributo y
    # el motor guarda el orden también al soltar en la MISMA columna.
    col = Path("el-taller/templates/proyectos/_kanban_columna.html").read_text(encoding="utf-8")
    assert '{% url \'proyectos-reordenar-kanban\' %}' in col
    assert "data-arr-zona" in col
    js = Path("el-taller/static/js/arrastrar.js").read_text(encoding="utf-8")
    assert "guardarOrden(zona)" in js


# ── (6) Próximos eventos del Dashboard ──────────────────────────────────────


def test_los_eventos_ya_no_dicen_compromiso(admin_user):
    from datetime import timedelta

    from apps.calendario.services import eventos_por_dia
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto
    from django.utils import timezone
    cli = Cliente.objects.create(razon_social="Kari Kari")
    manana = timezone.localdate() + timedelta(days=1)
    Proyecto.objects.create(
        nombre="Gorras", cliente=cli, estado="en_proceso_diseno",
        fecha_compromiso=timezone.make_aware(
            timezone.datetime.combine(manana, timezone.datetime.min.time())
        ),
    )
    evs = eventos_por_dia(admin_user, manana, manana)[manana]
    entrega = next(e for e in evs if e["tipo"] == "entrega")
    assert "Compromiso" not in entrega["titulo"]
    assert entrega["titulo"] == "📦 Gorras"
    assert entrega["estado"] == "en_proceso_diseno"


@pytest.mark.parametrize(("estado", "sale"), [
    ("por_cotizar", False),
    ("esperando_respuesta", False),
    ("en_proceso_diseno", True),
    ("en_proceso_produccion", True),
    ("entregado", True),
])
def test_proximos_eventos_solo_de_diseno_en_adelante(admin_user, estado, sale):
    from datetime import timedelta

    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto
    from apps.taller_home.views import _proximos_eventos
    from django.utils import timezone
    cli = Cliente.objects.create(razon_social="Kari Kari")
    manana = timezone.localdate() + timedelta(days=1)
    Proyecto.objects.create(
        nombre="Gorras", cliente=cli, estado=estado,
        fecha_compromiso=timezone.make_aware(
            timezone.datetime.combine(manana, timezone.datetime.min.time())
        ),
    )
    items, _mas = _proximos_eventos(admin_user)
    entregas = [i for i in items if i["tipo"] == "entrega"]
    assert bool(entregas) is sale


def test_el_calendario_completo_sigue_mostrando_todo(admin_user):
    """La regla es SÓLO del widget del Dashboard (decisión Oscar)."""
    from datetime import timedelta

    from apps.calendario.services import eventos_por_dia
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto
    from django.utils import timezone
    cli = Cliente.objects.create(razon_social="Kari Kari")
    manana = timezone.localdate() + timedelta(days=1)
    Proyecto.objects.create(
        nombre="Aún por cotizar", cliente=cli, estado="por_cotizar",
        fecha_compromiso=timezone.make_aware(
            timezone.datetime.combine(manana, timezone.datetime.min.time())
        ),
    )
    evs = eventos_por_dia(admin_user, manana, manana)[manana]
    assert any(e["tipo"] == "entrega" for e in evs)


def test_la_regla_sale_del_catalogo_de_estados():
    from apps.los_proyectos.models import slugs_con_compromiso_visible
    slugs = slugs_con_compromiso_visible()
    assert "en_proceso_diseno" in slugs and "entregado" in slugs
    assert "por_cotizar" not in slugs and "esperando_respuesta" not in slugs


# ── (7) UI: Guardar flotante, buscador, Chalán gris, tabita, comentarios ────


def test_el_guardar_flota_arriba_a_la_derecha_en_las_dos_apps():
    taller = Path("el-taller/static/js/ui.js").read_text(encoding="utf-8")
    gerencia = Path("la-gerencia/static/js/ui.js").read_text(encoding="utf-8")
    assert taller == gerencia, "ui.js es dual-copy (regla §18)"
    assert "data-guardar-flotante" in taller
    assert "fixed right-4 top-" in taller
    # No clona ni mueve el botón: hace click en el real (HTMX/form intactos).
    # LC 2026-08-07: ahora es un proxy por botón del grupo, así que el click va
    # a `real` en vez de a `original` — ver test_ajustes_ago07.py.
    assert "real.click()" in taller
    assert "data-sin-guardar-flotante" in taller  # opt-out
    assert "#modal-slot" in taller                # los modales no participan


def test_el_buscador_del_dashboard_no_lleva_texto_grande():
    home = Path("el-taller/templates/taller_home/home.html").read_text(encoding="utf-8")
    ini = home.index('id="kanban-buscar"')
    campo = home[ini:home.index(">", home.index("class=", ini))]
    assert "text-sm" in campo and "text-base" not in campo


def test_los_botones_de_redactar_del_chalan_son_grises():
    for ruta in ("_ia_bar.html", "_textarea_ia.html"):
        tpl = Path(f"el-taller/templates/_componentes_tailadmin/{ruta}").read_text(encoding="utf-8")
        ini = tpl.index("data-ia-redactar")
        boton = tpl[ini:tpl.index("</button>", ini)]
        assert "bg-brand-500" not in boton, ruta
        assert "bg-gray-100" in boton, ruta
        assert "🤖" in boton, ruta  # el robotcito azulito se queda


def test_la_tabita_de_crear_producto_se_lee():
    detalle = TPL_DETALLE.read_text(encoding="utf-8")
    bloque = detalle[detalle.index("Crear producto nuevo en el catálogo"):detalle.index("qc-msg")]
    assert "Categoría…" in bloque                      # se ve la palabra
    assert 'placeholder="Cant."' in bloque             # y ya no un «1» pelón
    assert 'placeholder="Merma"' in bloque
    assert 'value="1"' not in bloque and 'value="0"' not in bloque
    assert "minmax(9rem" in bloque                     # Categoría con ancho mínimo


def test_los_botones_de_nuevo_movimiento_viven_en_su_recuadro():
    detalle = TPL_DETALLE.read_text(encoding="utf-8")
    bloque = detalle[detalle.index(">Ingresos y egresos<"):detalle.index("Pagos pendientes sin registrar")]
    # Cada botón va DESPUÉS del encabezado de su propio recuadro.
    assert bloque.index(">Ingresos<") < bloque.index("+ Nuevo ingreso")
    assert bloque.index(">Egresos<") < bloque.index("+ Nuevo egreso")
    assert bloque.index("+ Nuevo ingreso") < bloque.index(">Egresos<")
    assert bloque.count("justify-center") >= 2  # centrados al pie


def test_los_comentarios_del_proyecto_son_compactos():
    tpl = Path("el-taller/templates/proyectos/_comentarios_panel.html").read_text(encoding="utf-8")
    assert "text-theme-xl" not in tpl          # el título baja de tamaño
    assert "_empty_state.html" not in tpl      # el vacío es un renglón
    assert "rows=2" in tpl


def test_la_cotizacion_muestra_su_version(client, admin_user, proyecto, catalogo):
    from apps.cotizaciones.models import Cotizacion
    cot = Cotizacion.objects.create(
        cliente=proyecto.cliente, proyecto=proyecto, version=3,
        titulo="Playeras", creado_por=admin_user,
    )
    client.force_login(admin_user)
    html = client.get(f"/cotizaciones/{cot.pk}/").content.decode()
    assert "v3" in html
