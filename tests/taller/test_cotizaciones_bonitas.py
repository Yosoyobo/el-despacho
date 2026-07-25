"""Cotizaciones bonitas (LC 2026-07) — alias del producto por proyecto y los
dos interruptores del documento.

El despacho compra «TShirt Oversize Color» a Crea Blanks y la vende como
«TShirt Modelo Janet»: el alias es lo que ve el cliente, el FK al catálogo
conserva de qué está hecha y a quién se le compra.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def entorno(usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(
        nombre="TShirt Oversize Color", precio_base="510", costo="180", categoria=cat)
    p = proyecto_factory(nombre="Paris, Texas", creado_por=admin)
    linea = ProyectoProducto.objects.create(
        proyecto=p, servicio=srv, cantidad=25, incluir_en_calculo=True)
    return {"admin": admin, "p": p, "srv": srv, "linea": linea, "cat": cat}


# ── Alias del producto dentro del proyecto ───────────────────────────────

class TestAlias:

    def test_sin_alias_usa_el_nombre_del_catalogo(self, entorno):
        assert entorno["linea"].nombre_visible == "TShirt Oversize Color"

    def test_con_alias_manda_el_alias(self, entorno):
        linea = entorno["linea"]
        linea.nombre_proyecto = "TShirt Modelo 'Janet'"
        linea.save(update_fields=["nombre_proyecto"])
        linea.refresh_from_db()
        assert linea.nombre_visible == "TShirt Modelo 'Janet'"
        # …y NO se pierde de qué está hecha ni a quién se le compra.
        assert linea.servicio_id == entorno["srv"].pk
        assert linea.nombre_catalogo == "TShirt Oversize Color"

    def test_alias_en_blancos_no_cuenta(self, entorno):
        linea = entorno["linea"]
        linea.nombre_proyecto = "   "
        assert linea.nombre_visible == "TShirt Oversize Color"

    def test_etiqueta_y_str_usan_el_alias(self, entorno):
        linea = entorno["linea"]
        linea.nombre_proyecto = "Janet"
        assert linea.etiqueta == "Janet ×25"
        assert str(linea) == "Janet ×25"

    def test_nombre_catalogo_no_duplica_la_variacion(self, entorno):
        """Higiene: si la variación ya trae el nombre del producto, no se repite."""
        from apps.el_catalogo.models import Variacion
        linea = entorno["linea"]
        linea.variacion = Variacion.objects.create(
            servicio=entorno["srv"], nombre="TShirt Oversize Color talla M")
        assert linea.nombre_catalogo == "TShirt Oversize Color talla M"

    def test_nombre_catalogo_concatena_variacion_distinta(self, entorno):
        from apps.el_catalogo.models import Variacion
        linea = entorno["linea"]
        linea.variacion = Variacion.objects.create(
            servicio=entorno["srv"], nombre="Talla M")
        assert linea.nombre_catalogo == "TShirt Oversize Color · Talla M"

    def test_el_alias_viaja_a_la_linea_de_la_cotizacion(self, entorno):
        """Lo que el cliente lee en el documento es el alias."""
        from apps.cotizaciones import services
        linea = entorno["linea"]
        linea.nombre_proyecto = "TShirt Modelo 'Janet'"
        linea.save(update_fields=["nombre_proyecto"])
        cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        assert cot.items.count() == 1
        assert cot.items.first().concepto == "TShirt Modelo 'Janet'"

    def test_kanban_busca_por_alias_y_por_nombre_de_catalogo(self, client, entorno):
        """Renombrar no debe romper «¿dónde uso la playera de Crea Blanks?».

        Sin apóstrofes en el alias: el HTML los escapa a `&#x27;` y el test
        estaría comparando contra otra cadena, no contra lo que se renderizó.
        """
        linea = entorno["linea"]
        linea.nombre_proyecto = "TShirt Modelo Janet"
        linea.save(update_fields=["nombre_proyecto"])
        client.force_login(entorno["admin"])
        resp = client.get("/proyectos/kanban/")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "tshirt modelo janet" in html.lower()
        assert "tshirt oversize color" in html.lower()


# ── El botón que renombra, en la tarjeta del proyecto ────────────────────

def _post_autosave(client, p, pp, srv, alias=""):
    """Simula el autosave HTMX del detalle (el formset de productos completo)."""
    return client.post(f"/proyectos/{p.pk}/", {
        "nombre": p.nombre, "cliente": p.cliente_id, "estado": p.estado,
        "descripcion": "",
        "productos-TOTAL_FORMS": "1", "productos-INITIAL_FORMS": "1",
        "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "1000",
        "productos-0-id": pp.pk,
        "productos-0-servicio": srv.pk,
        "productos-0-nombre_proyecto": alias,
        "productos-0-cantidad": "25",
        "productos-0-merma": "0",
        "productos-0-precio_unitario": "",
        "productos-0-costo_unitario": "",
        "productos-0-nota": "",
        "productos-0-procesos_json": "[]",
        "productos-0-incluir_en_calculo": "on",
    }, follow=True, HTTP_HX_REQUEST="true")


class TestBotonAlias:

    def test_la_tarjeta_trae_el_boton_y_el_campo(self, client, entorno):
        client.force_login(entorno["admin"])
        resp = client.get(f"/proyectos/{entorno['p'].pk}/")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "data-alias-toggle" in html
        assert "data-alias-input" in html
        assert "productos-0-nombre_proyecto" in html

    # Ojo: el <template> de la tarjeta vacía siempre aporta un bloque con
    # `hidden`, así que la señal fiable es la AUSENCIA/PRESENCIA de un bloque
    # SIN `hidden` (que solo puede venir de una línea que ya tiene alias).
    VISIBLE = 'data-alias-campo class="mb-1.5"'

    def test_el_campo_nace_oculto_si_no_hay_alias(self, client, entorno):
        client.force_login(entorno["admin"])
        html = client.get(f"/proyectos/{entorno['p'].pk}/").content.decode()
        assert 'data-alias-campo class="hidden' in html
        assert self.VISIBLE not in html

    def test_el_campo_nace_visible_si_ya_hay_alias(self, client, entorno):
        linea = entorno["linea"]
        linea.nombre_proyecto = "Janet"
        linea.save(update_fields=["nombre_proyecto"])
        client.force_login(entorno["admin"])
        html = client.get(f"/proyectos/{entorno['p'].pk}/").content.decode()
        assert self.VISIBLE in html
        assert "usa: TShirt Oversize Color" in html

    def test_el_autosave_guarda_el_alias(self, client, entorno):
        client.force_login(entorno["admin"])
        resp = _post_autosave(client, entorno["p"], entorno["linea"],
                              entorno["srv"], alias="TShirt Modelo Janet")
        assert resp.status_code == 200
        entorno["linea"].refresh_from_db()
        assert entorno["linea"].nombre_proyecto == "TShirt Modelo Janet"
        assert entorno["linea"].nombre_visible == "TShirt Modelo Janet"

    def test_el_autosave_puede_limpiar_el_alias(self, client, entorno):
        linea = entorno["linea"]
        linea.nombre_proyecto = "Janet"
        linea.save(update_fields=["nombre_proyecto"])
        client.force_login(entorno["admin"])
        _post_autosave(client, entorno["p"], linea, entorno["srv"], alias="")
        linea.refresh_from_db()
        assert linea.nombre_proyecto == ""
        assert linea.nombre_visible == "TShirt Oversize Color"


# ── Descripción: esqueleto, congelado y herencia ─────────────────────────

class TestDescripcion:

    def test_esqueleto_lleva_piezas_y_lo_del_catalogo(self, entorno):
        from apps.cotizaciones import descripcion
        srv = entorno["srv"]
        srv.descripcion_default = "100% algodón, oversize heavyweight 250 gsm"
        srv.save(update_fields=["descripcion_default"])
        texto = descripcion.esqueleto(entorno["linea"])
        assert texto.splitlines() == [
            "25 pz",
            "100% algodón, oversize heavyweight 250 gsm",
        ]

    def test_esqueleto_sin_descripcion_de_catalogo_es_solo_piezas(self, entorno):
        from apps.cotizaciones import descripcion
        assert descripcion.esqueleto(entorno["linea"]) == "25 pz"

    def test_la_merma_no_se_cotiza(self, entorno):
        """Las piezas del documento son las que se cobran, sin merma."""
        from apps.cotizaciones import descripcion
        linea = entorno["linea"]
        linea.merma = 5
        assert descripcion.esqueleto(linea).startswith("25 pz")

    def test_refrescar_piezas_preserva_el_parentesis(self, entorno):
        """Lo que Oscar escribió a mano entre paréntesis se respeta."""
        from apps.cotizaciones import descripcion
        linea = entorno["linea"]
        linea.cantidad = 110
        texto = descripcion.refrescar_piezas(
            "105 pz (3 colores, 35 pz c/u)\nGorras de gabardina", linea)
        assert texto.splitlines()[0] == "110 pz (3 colores, 35 pz c/u)"
        assert "Gorras de gabardina" in texto

    def test_refrescar_piezas_antepone_si_no_habia_conteo(self, entorno):
        from apps.cotizaciones import descripcion
        texto = descripcion.refrescar_piezas("Gorras de gabardina", entorno["linea"])
        assert texto.splitlines() == ["25 pz", "Gorras de gabardina"]

    def test_la_siguiente_version_hereda_el_texto_editado(self, entorno):
        """El branding escrito a mano en la v1 no se reescribe en la v2."""
        from apps.cotizaciones import services
        v1 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        it1 = v1.items.first()
        it1.descripcion = (
            "25 pz (2 tallas)\n"
            "100% algodón oversize\n"
            "Con impresión en serigrafía 7 x 4 con tintas de descarga"
        )
        it1.save(update_fields=["descripcion"])
        v2 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        it2 = v2.items.first()
        assert "serigrafía 7 x 4" in it2.descripcion
        assert "(2 tallas)" in it2.descripcion

    def test_al_heredar_se_refrescan_las_piezas(self, entorno):
        from apps.cotizaciones import services
        from apps.los_proyectos.models import ProyectoProducto
        v1 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        it1 = v1.items.first()
        it1.descripcion = "25 pz (2 tallas)\nCon bordado frontal"
        it1.save(update_fields=["descripcion"])
        ProyectoProducto.objects.filter(pk=entorno["linea"].pk).update(cantidad=40)
        v2 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        texto = v2.items.first().descripcion
        assert texto.splitlines()[0] == "40 pz (2 tallas)"
        assert "Con bordado frontal" in texto

    def test_el_texto_de_una_version_no_cambia_al_generar_otra(self, entorno):
        """Congelado por versión: la v1 queda tal cual quedó."""
        from apps.cotizaciones import services
        v1 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        it1 = v1.items.first()
        it1.descripcion = "25 pz\nTexto de la v1"
        it1.save(update_fields=["descripcion"])
        services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        it1.refresh_from_db()
        assert it1.descripcion == "25 pz\nTexto de la v1"

    def test_concepto_visible_es_retrocompatible(self, entorno):
        """Líneas viejas: el nombre vivía como único renglón de descripcion."""
        from apps.cotizaciones import services
        cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        it = cot.items.first()
        it.concepto = ""
        it.descripcion = "Gorras"
        it.save(update_fields=["concepto", "descripcion"])
        assert it.concepto_visible == "Gorras"
        # Y no se repite como especificación debajo del título.
        assert it.detalle_lineas == []

    def test_detalle_lineas_ignora_renglones_vacios(self, entorno):
        from apps.cotizaciones import services
        cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        it = cot.items.first()
        it.concepto = "Gorras"
        it.descripcion = "105 pz\n\n  Color: Beige  \n"
        it.save(update_fields=["concepto", "descripcion"])
        assert it.detalle_lineas == ["105 pz", "Color: Beige"]


# ── Interruptores del documento ──────────────────────────────────────────

class TestToggles:

    def test_defaults_conservadores(self, entorno):
        from apps.cotizaciones import services
        cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        assert cot.incluir_desglose is False
        assert cot.forma_pago == "anticipo"

    def test_nota_un_solo_pago(self, entorno):
        from apps.cotizaciones import services
        cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        cot.forma_pago = "contado"
        assert cot.nota_forma_pago == "Forma de pago: Un sólo pago."

    def test_nota_anticipo_default_50(self, entorno):
        from apps.cotizaciones import services
        cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        assert cot.nota_forma_pago == "Forma de pago: Anticipo 50%."

    def test_nota_anticipo_respeta_porcentaje_propio(self, entorno):
        from apps.cotizaciones import services
        cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        cot.anticipo_porcentaje = Decimal("40.00")
        assert cot.nota_forma_pago == "Forma de pago: Anticipo 40%."

    def test_nota_anticipo_con_fraccion(self, entorno):
        from apps.cotizaciones import services
        cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        cot.anticipo_porcentaje = Decimal("33.50")
        assert cot.nota_forma_pago == "Forma de pago: Anticipo 33.5%."

    def test_la_siguiente_version_hereda_los_interruptores(self, entorno):
        """Si ya decidiste desglose + un solo pago, la v2 no lo vuelve a preguntar."""
        from apps.cotizaciones import services
        v1 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        v1.incluir_desglose = True
        v1.forma_pago = "contado"
        v1.anticipo_porcentaje = Decimal("40.00")
        v1.save(update_fields=["incluir_desglose", "forma_pago", "anticipo_porcentaje"])
        v2 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        assert v2.version == v1.version + 1
        assert v2.incluir_desglose is True
        assert v2.forma_pago == "contado"
        assert v2.anticipo_porcentaje == Decimal("40.00")
