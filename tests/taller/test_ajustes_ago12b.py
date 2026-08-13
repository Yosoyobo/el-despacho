"""Pestañas por versión en «Productos involucrados» (S-Ajustes-Ago12-B, Oscar).

Oscar: «las tabs v1/v2/etc son para ver/cambiar productos involucrados que
llegaron a ser guardadas dentro del proyecto bajo cada cotización (v) se debería
de guardar todo siempre. A las cotizaciones en sí no agregaremos datos de merma,
costos, proveedores, ya que las cotizaciones son de salida y vista de clientes.»

Cubre:

* Al generar una versión se congela la foto COMPLETA (merma, costo, proveedor,
  procesos de producción y de venta), que es lo que el documento no guarda.
* La foto no se mueve cuando el catálogo cambia (un nulo es *desconocido*, no
  *heredado*).
* El panel de la pestaña: las mismas tarjetas, con la foto de solo lectura y sin
  asa de arrastre; el bloque vivo nunca sale del DOM.
* Se guarda con el MISMO autoguardado del proyecto (prefijo `ppv`) y lo que ve el
  cliente se empuja al documento — incluidas las líneas de venta y los borrados.
* «Restaurar en edición» repone valores sin borrar lo que el proyecto agregó
  después, y empareja por NOMBRE (dos alias del mismo producto del catálogo).
* La normalización de procesos/ventas quedó compartida con la línea viva.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

TPL_TABS = Path("el-taller/templates/proyectos/_productos_tabs.html")
TPL_DETALLE = Path("el-taller/templates/proyectos/detalle.html")
TPL_CARD = Path("el-taller/templates/proyectos/_producto_card.html")
TPL_JS = Path("el-taller/templates/proyectos/_form_productos_js.html")

BASE_FORMSET = {
    "productos-TOTAL_FORMS": "0", "productos-INITIAL_FORMS": "0",
    "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "50",
}


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def catalogo():
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="Producción", defaults={"orden": 10})
    prov = Proveedor.objects.create(razon_social="Crea Blanks", activo=True)
    srv = Servicio.objects.create(
        nombre="Playera Dry Fit", precio_base="220", costo="44.94", categoria=cat)
    return {"cat": cat, "prov": prov, "srv": srv}


@pytest.fixture
def entorno(usuario_factory, proyecto_factory, catalogo):
    """Un proyecto con una línea completa: merma, costo, proveedor, impresión y
    un proceso de venta. Es el caso que el documento NO sabe guardar."""
    from apps.los_proyectos.models import (
        ProyectoProducto,
        ProyectoProductoProceso,
        ProyectoProductoVenta,
    )
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Jeep Parte 1", creado_por=admin)
    linea = ProyectoProducto.objects.create(
        proyecto=p, servicio=catalogo["srv"], proveedor=catalogo["prov"],
        nombre_proyecto="Playera Janet", cantidad=29, merma=1,
        precio_unitario=Decimal("220.00"), costo_unitario=Decimal("44.94"),
        nota="105 pz (3 colores)\nColor: Beige", incluir_en_calculo=True,
    )
    ProyectoProductoProceso.objects.create(
        producto=linea, tipo="impresion", proveedor=catalogo["prov"],
        costo=Decimal("39.00"), por_pieza=True, orden=0)
    ProyectoProductoProceso.objects.create(
        producto=linea, tipo="operativo", descripcion="Adaptación y positivos",
        costo=Decimal("150.00"), por_pieza=False, orden=1)
    ProyectoProductoVenta.objects.create(
        producto=linea, descripcion="Ponchado", cantidad=1,
        precio_unitario=Decimal("350.00"), orden=0)
    return {"admin": admin, "p": p, "linea": linea, **catalogo}


@pytest.fixture
def cot(entorno):
    from apps.cotizaciones import services
    return services.generar_desde_proyecto(entorno["p"], entorno["admin"])


def _fila(cot):
    return cot.productos_version.get()


# ── Fotografiar al generar ───────────────────────────────────────────────────


def test_generar_congela_el_lado_del_costo(entorno, cot):
    """Lo que la cotización no guarda: merma, costo, proveedor y procesos."""
    fila = _fila(cot)
    assert fila.cantidad == 29
    assert fila.merma == 1
    assert fila.costo_unitario == Decimal("44.94")
    assert fila.precio_unitario == Decimal("220.00")
    assert fila.proveedor_id == entorno["prov"].pk
    assert fila.nombre_proyecto == "Playera Janet"
    assert fila.nota.startswith("105 pz")
    assert fila.reconstruido is False
    # Los procesos viajan como LISTA (la forma que serializa la tarjeta).
    assert isinstance(fila.procesos_json, list)
    tipos = [p["tipo"] for p in fila.procesos_json]
    assert tipos == ["impresion", "operativo"]
    assert fila.procesos_json[0]["costo"] == "39.00"
    assert fila.procesos_json[0]["por_pieza"] is True
    assert fila.procesos_json[1]["descripcion"] == "Adaptación y positivos"
    assert fila.ventas_json == [
        {"descripcion": "Ponchado", "cantidad": 1, "precio": "350.00"}]


def test_la_foto_queda_ligada_a_su_linea_del_documento(cot):
    fila = _fila(cot)
    item = cot.items.filter(agrupado=False).get()
    assert fila.item_id == item.pk
    assert item.concepto == "Playera Janet"


def test_la_foto_no_hereda_el_egreso(entorno, cot):
    """El FK `egreso` es marca de idempotencia de la línea viva; copiarlo haría
    que un gasto ya registrado se viera como registrado también en la foto."""
    fila = _fila(cot)
    assert not hasattr(fila, "egreso_id")


def test_la_foto_no_se_mueve_si_cambia_el_catalogo(entorno, cot):
    """Un nulo en la foto es *desconocido*, no *heredado*: si cayera al catálogo,
    el precio de hoy reescribiría lo que se cotizó ayer."""
    srv = entorno["srv"]
    srv.precio_base = Decimal("999.00")
    srv.costo = Decimal("777.00")
    srv.save()
    fila = _fila(cot)
    assert fila.precio_efectivo == Decimal("220.00")
    assert fila.costo_efectivo == Decimal("44.94")


def test_una_foto_sin_costo_no_inventa_el_del_catalogo(entorno, cot):
    fila = _fila(cot)
    fila.costo_unitario = None
    fila.save()
    assert fila.costo_efectivo == Decimal("0.00")


def test_dos_versiones_tienen_su_propia_foto(entorno, cot):
    from apps.cotizaciones import services
    entorno["linea"].cantidad = 40
    entorno["linea"].save()
    cot2 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    assert _fila(cot).cantidad == 29
    assert _fila(cot2).cantidad == 40


def test_no_se_puede_duplicar_la_foto_de_una_linea(cot):
    """La restricción parcial `(cotizacion, item)` da idempotencia de regalo."""
    from apps.los_proyectos.models import ProyectoProductoVersion
    from django.db import IntegrityError

    fila = _fila(cot)
    with pytest.raises(IntegrityError):
        ProyectoProductoVersion.objects.create(
            cotizacion=cot, item=fila.item, orden=9)


# ── El panel de la pestaña ───────────────────────────────────────────────────


def test_las_pestanas_salen_en_el_detalle(client, entorno, cot):
    client.force_login(entorno["admin"])
    html = client.get(reverse("proyectos-detalle", args=[entorno["p"].pk])).content.decode()
    assert "En edición" in html
    assert 'id="productos-vivo"' in html
    assert 'id="productos-version"' in html
    assert reverse("proyectos-productos-version",
                   args=[entorno["p"].pk, cot.pk]) in html


def test_sin_versiones_no_hay_pestanas(client, entorno):
    client.force_login(entorno["admin"])
    html = client.get(reverse("proyectos-detalle", args=[entorno["p"].pk])).content.decode()
    assert "En edición" not in html


def test_el_panel_trae_la_tarjeta_con_la_foto_de_solo_lectura(client, entorno, cot):
    client.force_login(entorno["admin"])
    html = client.get(
        reverse("proyectos-productos-version", args=[entorno["p"].pk, cot.pk]),
        HTTP_HX_REQUEST="true").content.decode()
    assert 'name="ppv_cotizacion"' in html
    assert "ppv-TOTAL_FORMS" in html
    assert "Playera Janet" in html
    # Foto visible pero no editable, y sin asa de arrastre.
    assert "data-img-slot" not in html
    assert "data-arr-asa" not in html
    # Los procesos de la foto se pintan desde el JSON.
    assert "Adaptación y positivos" in html
    assert "Ponchado" in html
    # Y el botón para reponerla en las líneas vivas.
    assert reverse("proyectos-version-restaurar",
                   args=[entorno["p"].pk, cot.pk]) in html


def test_el_panel_avisa_cuando_los_costos_son_reconstruidos(client, entorno, cot):
    fila = _fila(cot)
    fila.reconstruido = True
    fila.save()
    client.force_login(entorno["admin"])
    html = client.get(
        reverse("proyectos-productos-version", args=[entorno["p"].pk, cot.pk]),
        HTTP_HX_REQUEST="true").content.decode()
    assert "sólo guarda lo que ve el cliente" in html


def test_una_version_de_otro_proyecto_no_se_abre(client, entorno, cot, proyecto_factory):
    otro = proyecto_factory(nombre="Otro")
    client.force_login(entorno["admin"])
    r = client.get(reverse("proyectos-productos-version", args=[otro.pk, cot.pk]),
                   HTTP_HX_REQUEST="true")
    assert r.status_code == 404


def test_sin_permiso_de_editar_no_se_abre_el_panel(client, entorno, cot, usuario_factory):
    nadie = usuario_factory(rol="miembro", email="nadie@lc.mx")
    client.force_login(nadie)
    r = client.get(reverse("proyectos-productos-version", args=[entorno["p"].pk, cot.pk]),
                   HTTP_HX_REQUEST="true")
    assert r.status_code in (403, 404)


def test_el_bloque_vivo_nunca_sale_del_dom(client, entorno, cot):
    """Si se sacara, su management form se iría con él y el autoguardado del
    proyecto se rompería. Las pestañas sólo lo esconden."""
    tabs = TPL_TABS.read_text(encoding="utf-8")
    assert "classList.toggle('hidden'" in tabs
    assert "productos-vivo" in tabs
    # Y los elementos se buscan al CLIC: el script corre antes de que existan
    # (están más abajo en la página), así que resolverlos al cargar daría null.
    assert "() => document.getElementById('productos-vivo')" in tabs
    detalle = TPL_DETALLE.read_text(encoding="utf-8")
    # El slot de la versión va DESPUÉS del bloque vivo (hay JS que busca el
    # primer management form de la página).
    assert detalle.index('id="productos-vivo"') < detalle.index('id="productos-version"')


def test_el_js_inicializa_tambien_las_tarjetas_de_la_version():
    js = TPL_JS.read_text(encoding="utf-8")
    assert "#formset-productos-version [data-card]" in js
    # Y el contador de formularios se busca acotado al bloque vivo.
    assert "#formset-productos input[name$=\"-TOTAL_FORMS\"]" in js


def test_la_tarjeta_respeta_los_dos_flags():
    card = TPL_CARD.read_text(encoding="utf-8")
    assert "{% if not sin_arrastre %}" in card
    assert "{% if solo_lectura_foto %}" in card


# ── Guardar la versión por el autoguardado del proyecto ─────────────────────


def _payload_version(cot, fila, **campos):
    """POST del detalle con la pestaña de una versión abierta."""
    datos = {
        "nombre": cot.proyecto.nombre, "cliente": cot.proyecto.cliente_id,
        "estado": cot.proyecto.estado,
        **BASE_FORMSET,
        "ppv_cotizacion": str(cot.pk),
        "ppv-TOTAL_FORMS": "1", "ppv-INITIAL_FORMS": "1",
        "ppv-MIN_NUM_FORMS": "0", "ppv-MAX_NUM_FORMS": "50",
        "ppv-0-id": str(fila.pk),
        "ppv-0-cotizacion": str(cot.pk),
        "ppv-0-servicio": str(fila.servicio_id or ""),
        "ppv-0-nombre_proyecto": fila.nombre_proyecto,
        "ppv-0-cantidad": str(fila.cantidad),
        "ppv-0-merma": str(fila.merma),
        "ppv-0-precio_unitario": str(fila.precio_unitario or ""),
        "ppv-0-costo_unitario": str(fila.costo_unitario or ""),
        "ppv-0-nota": fila.nota,
        "ppv-0-orden": str(fila.orden),
        "ppv-0-incluir_en_calculo": "on",
        "ppv-0-procesos_json": json.dumps(fila.procesos_json),
        "ppv-0-ventas_json": json.dumps(fila.ventas_json),
    }
    datos.update(campos)
    return datos


def test_editar_la_version_guarda_la_foto_y_empuja_al_documento(client, entorno, cot):
    fila = _fila(cot)
    client.force_login(entorno["admin"])
    r = client.post(
        reverse("proyectos-detalle", args=[entorno["p"].pk]),
        _payload_version(cot, fila, **{
            "ppv-0-cantidad": "35",
            "ppv-0-merma": "3",
            "ppv-0-precio_unitario": "240.00",
            "ppv-0-nombre_proyecto": "Playera Janet v2",
            "ppv-0-nota": "35 pz\nColor: Negro",
        }),
        HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    fila.refresh_from_db()
    assert fila.cantidad == 35 and fila.merma == 3
    assert fila.precio_unitario == Decimal("240.00")
    # Y el documento de esa versión sigue a su pestaña.
    item = cot.items.filter(agrupado=False).get()
    assert item.concepto == "Playera Janet v2"
    assert item.cantidad == Decimal("35.00")
    assert item.precio_unitario == Decimal("240.00")
    assert "Color: Negro" in item.descripcion


def test_la_cuenta_escrita_en_el_costo_la_resuelve_el_servidor(client, entorno, cot):
    fila = _fila(cot)
    client.force_login(entorno["admin"])
    client.post(reverse("proyectos-detalle", args=[entorno["p"].pk]),
                _payload_version(cot, fila, **{"ppv-0-costo_unitario": "15.75*2"}),
                HTTP_HX_REQUEST="true")
    fila.refresh_from_db()
    assert fila.costo_unitario == Decimal("31.50")
    assert fila.costo_unitario_expr == "15.75*2"


def test_los_procesos_de_la_version_se_normalizan_al_guardar(client, entorno, cot):
    fila = _fila(cot)
    procesos = [{"tipo": "operativo", "descripcion": "Envío",
                 "costo": "0", "costo_expr": "40+60", "por_pieza": False}]
    client.force_login(entorno["admin"])
    client.post(reverse("proyectos-detalle", args=[entorno["p"].pk]),
                _payload_version(cot, fila,
                                 **{"ppv-0-procesos_json": json.dumps(procesos)}),
                HTTP_HX_REQUEST="true")
    fila.refresh_from_db()
    assert len(fila.procesos_json) == 1
    # El total lo saca el SERVIDOR de la cuenta escrita, no el front.
    assert fila.procesos_json[0]["costo"] == "100.00"
    assert fila.procesos_json[0]["costo_expr"] == "40+60"


def test_las_lineas_de_venta_se_resincronizan_en_el_documento(client, entorno, cot):
    fila = _fila(cot)
    ventas = [{"descripcion": "Ponchado", "cantidad": 1, "precio": "400.00"},
              {"descripcion": "Diseño de arte", "cantidad": 2, "precio": "150.00"}]
    client.force_login(entorno["admin"])
    client.post(reverse("proyectos-detalle", args=[entorno["p"].pk]),
                _payload_version(cot, fila,
                                 **{"ppv-0-ventas_json": json.dumps(ventas)}),
                HTTP_HX_REQUEST="true")
    agrupadas = list(cot.items.filter(agrupado=True).order_by("orden"))
    assert [a.concepto for a in agrupadas] == ["Ponchado", "Diseño de arte"]
    assert agrupadas[0].precio_unitario == Decimal("400.00")
    assert agrupadas[1].cantidad == Decimal("2.00")


def test_quitar_un_producto_de_la_version_lo_quita_del_documento(client, entorno, cot):
    fila = _fila(cot)
    client.force_login(entorno["admin"])
    client.post(reverse("proyectos-detalle", args=[entorno["p"].pk]),
                _payload_version(cot, fila, **{"ppv-0-DELETE": "on"}),
                HTTP_HX_REQUEST="true")
    assert cot.productos_version.count() == 0
    # La foto se fue; el documento no se toca sin filas (no se vacía de golpe).
    assert cot.items.exists()


def test_un_ppv_cotizacion_basura_no_tumba_el_guardado(client, entorno, cot):
    """Un POST manipulado: `filter(pk="x")` levantaría ValueError (500)."""
    fila = _fila(cot)
    client.force_login(entorno["admin"])
    r = client.post(reverse("proyectos-detalle", args=[entorno["p"].pk]),
                    _payload_version(cot, fila, ppv_cotizacion="no-soy-un-numero"),
                    HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    fila.refresh_from_db()
    assert fila.cantidad == 29  # se ignoró la pestaña, no se tocó la foto


def test_una_version_de_otro_proyecto_en_el_post_se_ignora(
        client, entorno, cot, proyecto_factory, usuario_factory):
    """No se puede editar la foto de otro proyecto pasando su pk en el POST."""
    from apps.cotizaciones import services
    ajeno = proyecto_factory(nombre="Ajeno")
    cot_ajena = services.generar_desde_proyecto(ajeno, entorno["admin"])
    fila = _fila(cot)
    client.force_login(entorno["admin"])
    r = client.post(reverse("proyectos-detalle", args=[entorno["p"].pk]),
                    _payload_version(cot, fila,
                                     ppv_cotizacion=str(cot_ajena.pk),
                                     **{"ppv-0-cantidad": "99"}),
                    HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    fila.refresh_from_db()
    assert fila.cantidad == 29


def test_el_autoguardado_del_proyecto_sigue_sin_la_pestana(client, entorno, cot):
    """Regresión: sin prefijo `ppv` el POST es el de siempre."""
    client.force_login(entorno["admin"])
    r = client.post(reverse("proyectos-detalle", args=[entorno["p"].pk]),
                    {"nombre": "Jeep Parte 1 bis",
                     "cliente": entorno["p"].cliente_id,
                     "estado": entorno["p"].estado, **BASE_FORMSET},
                    HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    entorno["p"].refresh_from_db()
    assert entorno["p"].nombre == "Jeep Parte 1 bis"


def test_un_autoguardado_invalido_avisa_en_vez_de_tronar(client, entorno):
    """Bug preexistente cazado en este sprint: el `@login_required` estaba pegado
    a `_primer_error` en lugar de a `detalle`, así que el decorador trataba al
    `form` como el `request` y la rama de error tiraba 500 (`AttributeError`) en
    vez de mostrar el aviso que V6 puso ahí."""
    client.force_login(entorno["admin"])
    linea = entorno["linea"]
    r = client.post(reverse("proyectos-detalle", args=[entorno["p"].pk]), {
        "nombre": entorno["p"].nombre, "cliente": entorno["p"].cliente_id,
        "estado": entorno["p"].estado,
        "productos-TOTAL_FORMS": "1", "productos-INITIAL_FORMS": "1",
        "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "50",
        "productos-0-id": str(linea.pk),
        "productos-0-servicio": str(linea.servicio_id),
        "productos-0-cantidad": "1",
        "productos-0-costo_unitario": "no-es-un-numero",
    }, HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert "Costo inválido" in r.content.decode()


# ── Restaurar en edición ─────────────────────────────────────────────────────


def test_restaurar_repone_los_valores_en_la_linea_viva(entorno, cot):
    from apps.los_proyectos import services_version
    linea = entorno["linea"]
    linea.cantidad = 5
    linea.merma = 0
    linea.precio_unitario = Decimal("100.00")
    linea.save()
    res = services_version.restaurar_en_edicion(cot, entorno["admin"])
    linea.refresh_from_db()
    assert res["actualizadas"] == 1 and res["creadas"] == 0
    assert linea.cantidad == 29 and linea.merma == 1
    assert linea.precio_unitario == Decimal("220.00")
    # Y sus procesos vuelven (los de producción y los de venta).
    assert linea.procesos.count() == 2
    assert linea.ventas.count() == 1


def test_restaurar_no_borra_lo_que_se_agrego_despues(entorno, cot, catalogo):
    """Una línea puede tener un egreso registrado: hacerla desaparecer dejaría el
    gasto colgando."""
    from apps.los_proyectos import services_version
    from apps.los_proyectos.models import ProyectoProducto
    extra = ProyectoProducto.objects.create(
        proyecto=entorno["p"], servicio=catalogo["srv"],
        nombre_proyecto="Gorra extra", cantidad=10)
    services_version.restaurar_en_edicion(cot, entorno["admin"])
    assert ProyectoProducto.objects.filter(pk=extra.pk).exists()


def test_restaurar_empareja_por_nombre_no_por_producto(entorno, cot, catalogo):
    """Dos alias del MISMO producto del catálogo comparten la llave por producto
    (lección de S-Ajustes-Jul29): manda el nombre."""
    from apps.los_proyectos import services_version
    from apps.los_proyectos.models import ProyectoProducto
    otra = ProyectoProducto.objects.create(
        proyecto=entorno["p"], servicio=catalogo["srv"],
        nombre_proyecto="Playera Blanca", cantidad=7,
        precio_unitario=Decimal("111.00"))
    services_version.restaurar_en_edicion(cot, entorno["admin"])
    otra.refresh_from_db()
    entorno["linea"].refresh_from_db()
    # La foto era de «Playera Janet»: la otra línea no se toca.
    assert otra.cantidad == 7 and otra.precio_unitario == Decimal("111.00")
    assert entorno["linea"].cantidad == 29


def test_restaurar_crea_la_linea_si_ya_no_esta(entorno, cot):
    from apps.los_proyectos import services_version
    entorno["linea"].delete()
    res = services_version.restaurar_en_edicion(cot, entorno["admin"])
    assert res["creadas"] == 1
    assert entorno["p"].productos.count() == 1
    nueva = entorno["p"].productos.get()
    assert nueva.nombre_proyecto == "Playera Janet"
    assert nueva.cantidad == 29
    assert nueva.procesos.count() == 2


def test_la_vista_de_restaurar_pide_permiso_y_redirige(client, entorno, cot,
                                                       usuario_factory):
    url = reverse("proyectos-version-restaurar", args=[entorno["p"].pk, cot.pk])
    nadie = usuario_factory(rol="miembro", email="nadie2@lc.mx")
    client.force_login(nadie)
    assert client.post(url).status_code in (403, 404)
    client.force_login(entorno["admin"])
    r = client.post(url, HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert r.headers["HX-Redirect"].endswith(f"/proyectos/{entorno['p'].pk}/")


# ── La normalización quedó compartida con la línea viva ─────────────────────


def test_normalizadores_devuelven_none_con_basura():
    from apps.los_proyectos.services_procesos import (
        procesos_normalizados,
        ventas_normalizadas,
    )
    for fn in (procesos_normalizados, ventas_normalizadas):
        assert fn(None) is None
        assert fn("{no es json") is None
        assert fn('{"no": "es lista"}') is None
        assert fn("[]") == []


class TestReconstruirLoYaCotizado:
    """La data migration `proyectos/0034` contra datos de verdad.

    Se le pasa el registro REAL de apps: la migración sólo usa `objects`, campos y
    relaciones —nunca properties, justo porque un modelo histórico no las trae— así
    que corre igual y se puede afirmar sobre el resultado.
    """

    @staticmethod
    def _reconstruir():
        import importlib.util

        from django.apps import apps as registro
        ruta = ("el-taller/apps/los_proyectos/migrations/"
                "0034_backfill_producto_version.py")
        spec = importlib.util.spec_from_file_location("bf34", ruta)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.reconstruir(registro, None)
        return mod

    def test_reconstruye_desde_el_documento_y_el_costo_de_hoy(self, entorno, cot):
        """Lo exacto sale de la cotización; el costo, de la línea que hay hoy."""
        cot.productos_version.all().delete()  # una versión «de antes del deploy»
        self._reconstruir()
        fila = _fila(cot)
        # Exacto, del documento.
        assert fila.cantidad == 29
        assert fila.precio_unitario == Decimal("220.00")
        assert fila.nombre_proyecto == "Playera Janet"
        # La especificación se toma del DOCUMENTO, que es la única que existía de
        # entonces — con su conteo de piezas ya refrescado al generar la versión
        # (29, no el «105 pz» que quedó escrito a mano en la tarjeta).
        assert fila.nota.startswith("29 pz")
        assert "Color: Beige" in fila.nota
        # Aproximado, de la línea viva — y marcado como tal.
        assert fila.reconstruido is True
        assert fila.merma == 1
        assert fila.costo_unitario == Decimal("44.94")
        assert fila.proveedor_id == entorno["prov"].pk
        assert len(fila.procesos_json) == 2
        # Las líneas `agrupado` del documento SON los procesos de venta.
        assert fila.ventas_json == [
            {"descripcion": "Ponchado", "cantidad": 1, "precio": "350.00"}]

    def test_es_idempotente(self, entorno, cot):
        cot.productos_version.all().delete()
        self._reconstruir()
        self._reconstruir()
        assert cot.productos_version.count() == 1

    def test_no_toca_una_version_ya_fotografiada(self, entorno, cot):
        fila = _fila(cot)
        self._reconstruir()
        assert cot.productos_version.count() == 1
        assert _fila(cot).pk == fila.pk
        assert _fila(cot).reconstruido is False

    def test_sin_linea_que_empareje_deja_el_costo_vacio(self, entorno, cot):
        """El producto ya se quitó del proyecto: no se inventa su costo."""
        cot.productos_version.all().delete()
        entorno["linea"].delete()
        self._reconstruir()
        fila = _fila(cot)
        assert fila.cantidad == 29                    # el documento sí lo sabe
        assert fila.costo_unitario is None            # el costo, no
        assert fila.merma == 0
        assert fila.proveedor_id is None
        assert fila.procesos_json == []

    def test_dos_alias_del_mismo_producto_no_se_cruzan(
            self, entorno, cot, catalogo, usuario_factory):
        """La llave `(servicio, variacion)` es ambigua con dos alias: manda el
        nombre, y una línea emparejada no se reutiliza (lección Jul29)."""
        from apps.cotizaciones import services
        from apps.los_proyectos.models import ProyectoProducto
        blanca = ProyectoProducto.objects.create(
            proyecto=entorno["p"], servicio=catalogo["srv"],
            nombre_proyecto="Playera Blanca", cantidad=7, merma=4,
            precio_unitario=Decimal("111.00"), costo_unitario=Decimal("22.00"),
            incluir_en_calculo=True)
        cot2 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
        cot2.productos_version.all().delete()
        self._reconstruir()
        filas = {f.nombre_proyecto: f for f in cot2.productos_version.all()}
        assert set(filas) == {"Playera Janet", "Playera Blanca"}
        # Cada una con SU costo y SU merma, no con los de la otra.
        assert filas["Playera Janet"].merma == 1
        assert filas["Playera Janet"].costo_unitario == Decimal("44.94")
        assert filas["Playera Blanca"].merma == 4
        assert filas["Playera Blanca"].costo_unitario == Decimal("22.00")
        assert blanca.pk  # sigue viva

    def test_una_cantidad_decimal_se_redondea_no_se_trunca(self, entorno, cot):
        cot.productos_version.all().delete()
        item = cot.items.filter(agrupado=False).get()
        item.cantidad = Decimal("2.50")
        item.save()
        self._reconstruir()
        assert _fila(cot).cantidad == 3

    def test_una_cotizacion_sin_proyecto_no_se_toca(self, entorno, cot):
        """Las standalone (version=0) quedan fuera: no tienen de dónde sacar costo."""
        from apps.cotizaciones.models import Cotizacion
        suelta = Cotizacion.objects.create(
            cliente=entorno["p"].cliente, titulo="Suelta", version=0)
        cot.productos_version.all().delete()
        self._reconstruir()
        assert suelta.productos_version.count() == 0


def test_sincronizar_procesos_sigue_funcionando(entorno):
    """Regresión de la extracción: la línea viva se sincroniza igual."""
    from apps.los_proyectos.services_procesos import sincronizar_procesos
    linea = entorno["linea"]
    sincronizar_procesos(linea, json.dumps([
        {"tipo": "operativo", "descripcion": "Fletes", "costo": 80, "por_pieza": False},
    ]))
    assert [p.descripcion for p in linea.procesos.all()] == ["Fletes"]
    # JSON ilegible: no toca nada.
    sincronizar_procesos(linea, "{roto")
    assert linea.procesos.count() == 1
