"""Ajustes de Oscar del 2026-07-26 (segunda ronda, VERSION 2026.07.33).

Cubre los 9 puntos del ticket:

1. Tecla Delete sobre el recuadro de imagen ⇒ desliga la foto (sin borrarla de
   Drive: puede estar congelada en una cotización enviada).
2. Documento PDF: cada bloque de producto y el desglose van dentro de una tabla
   envoltorio (lo único que Docs no corta entre páginas), el título del desglose
   es la primera fila de SU tabla, y hay un `<br>` entre el logo y el título.
3. Ficha del cliente: la pastilla de referencia usa el slug REAL y no sale tachada.
4. Fila «Sin información» con botón «Agregar +» que precarga el folio del hueco.
5. Tabla de facturas: Emisión en 2.º lugar + columnas ✓/✕ de PDF, XML y proyecto.
6. «+ Proceso» de VENTA en la tarjeta de producto: se cobra aparte y viaja a la
   cotización como línea propia, impresa dentro de la tabla de su producto.
7. Kanban: las columnas de cierre no pintan las pastillas de productos.
8. Resumen de pendientes: TIZAYUCA ignora proyectos que ya no se producen.
9. Pagos pendientes agrupados por proveedor: un solo pago por proveedor.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _servicio(nombre="Bordado", precio="100.00", costo="40.00"):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat Jul26")
    return Servicio.objects.create(
        nombre=nombre, categoria=cat, precio_base=Decimal(precio),
        costo=Decimal(costo), activo=True,
    )


def _login(client, usuario_factory, rol="super_admin"):
    u = usuario_factory(rol=rol)
    client.force_login(u)
    return u


# ── 1 · Delete desliga la imagen ─────────────────────────────────────────


def test_delete_quita_la_foto_propia_del_uso(client, usuario_factory, proyecto_factory):
    """La línea con foto propia la pierde y vuelve a heredar la del catálogo."""
    from apps.los_proyectos.models import ProyectoProducto

    _login(client, usuario_factory)
    srv = _servicio()
    srv.imagen_file_id = "cat-123"
    srv.save(update_fields=["imagen_file_id"])
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=srv, cantidad=1,
        nombre_proyecto="Alias del proyecto", imagen_file_id="uso-999",
    )
    r = client.post(f"/proyectos/producto/{pp.pk}/imagen", {"quitar": "1"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    pp.refresh_from_db()
    srv.refresh_from_db()
    assert pp.imagen_file_id == ""
    # La del catálogo NO se toca: la línea vuelve a heredarla.
    assert srv.imagen_file_id == "cat-123"
    assert pp.imagen_efectiva_file_id == "cat-123"


def test_delete_sobre_foto_heredada_quita_la_del_catalogo(
        client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto

    _login(client, usuario_factory)
    srv = _servicio()
    srv.imagen_file_id = "cat-123"
    srv.save(update_fields=["imagen_file_id"])
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=1)
    r = client.post(f"/proyectos/producto/{pp.pk}/imagen", {"quitar": "1"})
    assert r.status_code == 200
    assert r.json()["destino"] == "catalogo"
    srv.refresh_from_db()
    assert srv.imagen_file_id == ""


def test_quitar_sin_foto_devuelve_error(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto

    _login(client, usuario_factory)
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(proyecto=p, servicio=_servicio(), cantidad=1)
    r = client.post(f"/proyectos/producto/{pp.pk}/imagen", {"quitar": "1"})
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_delete_quita_la_foto_del_producto_del_catalogo(client, usuario_factory):
    _login(client, usuario_factory)
    srv = _servicio()
    srv.imagen_file_id = "cat-abc"
    srv.save(update_fields=["imagen_file_id"])
    r = client.post(f"/catalogo/{srv.pk}/imagen", {"quitar": "1"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    srv.refresh_from_db()
    assert srv.imagen_file_id == ""


def test_js_de_imagen_cablea_la_tecla_delete():
    """El JS es dual-copy sólo en el Taller; se valida el contrato del handler."""
    from pathlib import Path
    js = Path("el-taller/static/js/imagen_pegar.js").read_text(encoding="utf-8")
    assert 'ev.key !== "Delete"' in js
    assert "data-img-compartida" in js  # confirma antes de tocar la del catálogo
    assert 'body.append("quitar", "1")' in js


# ── 2 · Documento PDF ────────────────────────────────────────────────────


def _cot_con_items(proyecto_factory, n=1):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    p = proyecto_factory()
    cot = Cotizacion.objects.create(cliente=p.cliente, proyecto=p, titulo="T",
                                    estado="borrador", version=1,
                                    incluir_desglose=True)
    for i in range(n):
        CotizacionItem.objects.create(
            cotizacion=cot, orden=i, concepto=f"Concepto {i}",
            cantidad=Decimal("2.00"), precio_unitario=Decimal("50.00"),
        )
    return cot


def test_pdf_envuelve_cada_bloque_para_que_no_se_parta(proyecto_factory):
    from apps.cotizaciones import services
    cot = _cot_con_items(proyecto_factory, n=2)
    html = services.construir_html_pdf(cot)
    # Tabla envoltorio de una sola celda: es lo único que Docs no corta.
    assert html.count('<tr><td style="border:none; padding:0; vertical-align:top;">') >= 3
    assert "page-break-inside:avoid" in html


def test_pdf_titulo_del_desglose_va_dentro_de_su_tabla(proyecto_factory):
    from apps.cotizaciones import services
    # LC 2026-08-04: la tabla del desglose necesita más de un producto (con uno
    # solo ya no se imprime — sería copia de la tablita de montos).
    cot = _cot_con_items(proyecto_factory, n=2)
    html = services.construir_html_pdf(cot)
    # El título es una fila colspan de la MISMA tabla (no un <p> suelto antes).
    # (El padding bajó a 10pt el 2026-07-28 y a 6pt el 2026-08-04, con las dos
    # rondas de «apretar el interlineado de todo».)
    assert '<td colspan="5" style="border:none; padding:0 0 6pt 0; text-align:center; font-size:12pt;">Desglose de Elementos</td>' in html
    assert '<p style="text-align:center; font-size:12pt; margin:34pt 0 14pt 0;">Desglose' not in html


def test_pdf_mete_un_br_entre_el_logo_y_el_titulo(proyecto_factory):
    from apps.cotizaciones import services
    cot = _cot_con_items(proyecto_factory)
    html = services.construir_html_pdf(cot)
    i_logo = html.find("Logo_LC-256.png")
    # El título es el <p> centrado que va tras el logo. LC 2026-07-26 (ronda 3):
    # ya no tiene tamaño propio —usa el del cuerpo—, así que se busca por su
    # texto en vez de por el `font-size`.
    i_titulo = html.find("Producción de elementos para proyecto", i_logo)
    assert i_logo != -1 and i_titulo != -1
    assert "<br>" in html[i_logo:i_titulo]


# ── 3 · Slug de la ficha del cliente ─────────────────────────────────────


def test_ficha_cliente_usa_el_slug_real_y_no_lo_tacha(
        client, usuario_factory, cliente_factory):
    from django.urls import reverse

    _login(client, usuario_factory)
    # El caso de Oscar: el cliente se registró como «Tessa» (slug `tessa`) y
    # después se le corrigió la razón social. El slug NO se regenera (preserva las
    # referencias históricas), así que slugificar la razón social inventaba
    # `$tessa-studio`, que no es su referencia.
    cli = cliente_factory(razon_social="Tessa")
    assert cli.slug == "tessa"
    cli.razon_social = "Tessa Studio"
    cli.save(update_fields=["razon_social"])

    r = client.get(reverse("cartera-detalle", args=[cli.pk]))
    assert r.status_code == 200
    html = r.content.decode()
    assert "$tessa" in html
    assert "$tessa-studio" not in html
    # …y la pastilla no sale tachada (activo=True).
    i = html.find("$tessa")
    assert "line-through" not in html[max(0, i - 700):i]


# ── 4 y 5 · Tabla de facturas ────────────────────────────────────────────


def _factura(cliente, folio, **kw):
    from apps.facturacion.models import Factura
    return Factura.objects.create(
        cliente=cliente, folio_numero=folio, concepto=kw.pop("concepto", "Servicio"),
        fecha_emision=date.today(), estado=kw.pop("estado", "borrador"), **kw)


def test_hueco_de_folio_ofrece_agregar_con_el_folio_precargado(
        client, usuario_factory, cliente_factory):
    _login(client, usuario_factory)
    cli = cliente_factory()
    _factura(cli, 101)
    _factura(cli, 103)          # deja el hueco 102
    r = client.get("/facturacion/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Sin información" in html
    assert "/facturacion/nueva/?folio=102" in html
    assert "Agregar +" in html


def test_nueva_factura_precarga_el_folio_del_querystring(client, usuario_factory):
    _login(client, usuario_factory)
    r = client.get("/facturacion/nueva/?folio=207")
    assert r.status_code == 200
    assert 'value="207"' in r.content.decode()


def test_lista_facturas_columnas_nuevas(client, usuario_factory, cliente_factory,
                                        proyecto_factory):
    _login(client, usuario_factory)
    cli = cliente_factory()
    p = proyecto_factory(cliente=cli)
    f1 = _factura(cli, 301, proyecto=p)
    f1.pdf_file_id = "pdf-1"
    f1.save(update_fields=["pdf_file_id"])
    _factura(cli, 302)          # sin PDF, sin XML, sin proyecto
    r = client.get("/facturacion/")
    html = r.content.decode()
    cabeceras = html.split("<thead")[1].split("</thead>")[0]
    # Cabeceras nuevas y el orden: Emisión antes que Cliente.
    for etiqueta in ("PDF", "XML", "Proyecto"):
        assert etiqueta in cabeceras
    assert cabeceras.find("Emisión") < cabeceras.find("Cliente")
    assert "PDF del CFDI almacenado" in html      # la que sí lo tiene
    assert "Falta el XML del CFDI" in html        # la que no
    assert "Sin proyecto ligado" in html


# ── 6 · Procesos de VENTA ────────────────────────────────────────────────


def test_proceso_de_venta_suma_al_monto_no_al_costo(proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.services_procesos import sincronizar_ventas

    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=10, incluir_en_calculo=True,
        precio_unitario=Decimal("100.00"), costo_unitario=Decimal("40.00"),
    )
    sincronizar_ventas(pp, json.dumps([
        {"descripcion": "Ponchado", "cantidad": 1, "precio": "350.00"},
    ]))
    pp.refresh_from_db()
    assert pp.subtotal == Decimal("1000.00")
    assert pp.subtotal_ventas == Decimal("350.00")
    assert pp.subtotal_con_ventas == Decimal("1350.00")
    # El costo NO se mueve: un proceso de venta no cuesta.
    assert pp.costo_total_con_procesos == Decimal("400.00")
    p.refresh_from_db()
    assert p.monto_calculado == Decimal("1350.00")


def test_sincronizar_ventas_reconcilia_y_es_defensivo(proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.services_procesos import sincronizar_ventas

    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(proyecto=p, servicio=_servicio(), cantidad=1)
    sincronizar_ventas(pp, json.dumps([
        {"descripcion": "Ponchado", "cantidad": 2, "precio": "100.00"},
        {"descripcion": "Arte", "cantidad": 1, "precio": "500.00"},
        {"descripcion": "", "cantidad": 1, "precio": "0"},   # fila vacía: se ignora
    ]))
    assert pp.ventas.count() == 2
    pks = sorted(v.pk for v in pp.ventas.all())
    # Reconcilia en sitio (no borra y recrea): el primer pk sobrevive.
    sincronizar_ventas(pp, json.dumps([
        {"descripcion": "Ponchado premium", "cantidad": 3, "precio": "120.00"},
    ]))
    assert pp.ventas.count() == 1
    v = pp.ventas.first()
    assert v.pk == pks[0]
    assert v.descripcion == "Ponchado premium"
    assert v.subtotal == Decimal("360.00")
    # JSON inválido no toca nada.
    sincronizar_ventas(pp, "{no es json")
    assert pp.ventas.count() == 1


def test_cotizacion_genera_el_proceso_de_venta_como_linea_agrupada(
        proyecto_factory, usuario_factory):
    from apps.cotizaciones import services
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.services_procesos import sincronizar_ventas

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=10, incluir_en_calculo=True,
        precio_unitario=Decimal("100.00"),
    )
    sincronizar_ventas(pp, json.dumps([
        {"descripcion": "Ponchado", "cantidad": 1, "precio": "350.00"}]))
    cot = services.generar_desde_proyecto(p, u)
    items = list(cot.items.order_by("orden"))
    assert len(items) == 2
    assert items[0].concepto == "Bordado" and items[0].agrupado is False
    assert items[1].concepto == "Ponchado" and items[1].agrupado is True
    # El total de la cotización incluye el proceso de venta.
    assert cot.calcular_totales()["subtotal_items"] == Decimal("1350.00")


def test_pdf_imprime_el_proceso_de_venta_en_la_tabla_de_su_producto(
        proyecto_factory, usuario_factory):
    from apps.cotizaciones import services
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.services_procesos import sincronizar_ventas

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=10, incluir_en_calculo=True,
        precio_unitario=Decimal("100.00"),
    )
    sincronizar_ventas(pp, json.dumps([
        {"descripcion": "Ponchado", "cantidad": 1, "precio": "350.00"}]))
    cot = services.generar_desde_proyecto(p, u)
    html = services.construir_html_pdf(cot)
    # La numeración de bloques cuenta PRODUCTOS: hay un «1.» y no hay «2.».
    conceptos = html.split("Desglose de Elementos")[0]
    assert 'vertical-align:top;">1.</td>' in conceptos
    assert 'vertical-align:top;">2.</td>' not in conceptos
    # «Ponchado» sale como renglón de la tabla de montos del Bordado.
    i_bordado = conceptos.find("Bordado")
    assert i_bordado != -1
    assert "Ponchado" in conceptos[i_bordado:]


def test_tarjeta_del_producto_ofrece_proceso_de_venta(
        client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto

    _login(client, usuario_factory)
    p = proyecto_factory()
    ProyectoProducto.objects.create(proyecto=p, servicio=_servicio(), cantidad=1)
    r = client.get(f"/proyectos/{p.pk}/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "venta-add" in html
    # El rótulo se retiró en el render del 2026-07-28: queda el botón verde con
    # su tooltip («Agrega una línea que se le COBRA al cliente…»).
    assert "se le COBRA al cliente" in html
    assert "ventas_json" in html


# ── 7 · Kanban ───────────────────────────────────────────────────────────


def test_kanban_no_pinta_productos_en_las_columnas_de_cierre(
        client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto

    _login(client, usuario_factory)
    activo = proyecto_factory(nombre="Vivo", estado="en_proceso_produccion")
    cerrado = proyecto_factory(nombre="Cerrado", estado="entregado")
    ProyectoProducto.objects.create(proyecto=activo, servicio=_servicio("Playera"), cantidad=3)
    ProyectoProducto.objects.create(proyecto=cerrado, servicio=_servicio("Gorra"), cantidad=7)
    html = client.get("/proyectos/kanban/").content.decode()
    # Las pastillas del proyecto cerrado se renderizan pero ocultas, con la marca
    # que el buscador usa para revelarlas en los resultados.
    assert "data-productos-colapsado" in html
    assert "7× Gorra" in html
    i = html.find("7× Gorra")
    assert "data-productos-colapsado" in html[max(0, i - 400):i]
    # El activo las pinta normal (sin la marca).
    j = html.find("3× Playera")
    assert "data-productos-colapsado" not in html[max(0, j - 400):j]


def test_buscador_del_kanban_revela_las_pastillas_ocultas():
    from pathlib import Path
    js = Path("el-taller/templates/proyectos/_kanban_script.html").read_text(encoding="utf-8")
    assert "[data-productos-colapsado]" in js
    assert "prods.classList.toggle('hidden', !(hay && q))" in js


# ── 8 · TIZAYUCA ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("estado", ["en_pausa", "entregado", "cerrado", "cancelado"])
def test_tizayuca_ignora_proyectos_que_ya_no_se_producen(
        estado, usuario_factory, proyecto_factory):
    from apps.el_catalogo.calculadora import PROVEEDOR_CALCULADORA
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos.models import ProyectoProducto
    from apps.taller_home.pendientes import secciones_pendientes

    u = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social=PROVEEDOR_CALCULADORA, activo=True)
    manana = date.today() + timedelta(days=3)
    vivo = proyecto_factory(nombre="Vivo", estado="en_proceso_produccion",
                            fecha_compromiso=manana)
    muerto = proyecto_factory(nombre="Muerto", estado=estado, fecha_compromiso=manana)
    for p in (vivo, muerto):
        ProyectoProducto.objects.create(
            proyecto=p, servicio=_servicio(f"Tote {p.pk}"), cantidad=5,
            proveedor=prov, incluir_en_calculo=True)
    tiza = next(s for s in secciones_pendientes(u) if s["titulo"] == "TIZAYUCA")
    texto = "\n".join(tiza["lineas"])
    assert "Vivo" in texto
    assert "Muerto" not in texto


# ── 9 · Pagos pendientes agrupados por proveedor ─────────────────────────


def _proyecto_con_gastos(proyecto_factory, prov):
    """Proyecto en producción con 2 productos y 1 proceso del MISMO proveedor."""
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.services_procesos import sincronizar_procesos

    p = proyecto_factory(estado="en_proceso_produccion")
    pp1 = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio("Tote"), cantidad=10, proveedor=prov,
        costo_unitario=Decimal("30.00"), incluir_en_calculo=True)
    ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio("Gorra"), cantidad=5, proveedor=prov,
        costo_unitario=Decimal("20.00"), incluir_en_calculo=True)
    sincronizar_procesos(pp1, json.dumps([
        {"tipo": "impresion", "proveedor_id": prov.pk, "costo": "5.00",
         "por_pieza": True}]))
    return p


def test_pagos_pendientes_se_agrupan_por_proveedor(proyecto_factory):
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos import gastos

    prov = Proveedor.objects.create(razon_social="Simil Cuero", activo=True)
    p = _proyecto_con_gastos(proyecto_factory, prov)
    unidades = gastos.pagos_pendientes_de(p)
    grupos = gastos.grupos_pagos_pendientes_de(p)
    # 3 unidades de gasto → 1 solo proveedor.
    assert len(unidades) == 3
    assert len(grupos) == 1
    g = grupos[0]
    assert g["clave"] == prov.pk
    assert len(g["unidades"]) == 3
    assert g["monto"] == sum(u["monto"] for u in unidades)


def test_registrar_pago_del_grupo_crea_un_solo_egreso(
        client, usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos import gastos
    from apps.tesoreria.models import CentroDeCosto, Egreso

    _login(client, usuario_factory)
    CentroDeCosto.objects.get_or_create(
        slug=gastos.CENTRO_SLUG, defaults={"nombre": "Insumos de proyecto"})
    prov = Proveedor.objects.create(razon_social="Simil Cuero", activo=True)
    p = _proyecto_con_gastos(proyecto_factory, prov)
    esperado = gastos.grupos_pagos_pendientes_de(p)[0]["monto"]

    antes = Egreso.objects.count()
    r = client.post(f"/proyectos/{p.pk}/pago-proveedor/{prov.pk}/registrar", {
        "fecha": date.today().isoformat(), "proveedor": str(prov.pk),
        "metodo": "transferencia", "estado_pago": "pagado",
    }, HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    # UN egreso para las 3 unidades, con la suma.
    assert Egreso.objects.count() == antes + 1
    eg = Egreso.objects.latest("pk")
    assert eg.monto == esperado
    assert eg.proveedor_id == prov.pk
    assert not gastos.pagos_pendientes_de(p)


def test_modal_del_grupo_enlista_los_conceptos(client, usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos import gastos

    _login(client, usuario_factory)
    CentroDeCosto = __import__("apps.tesoreria.models", fromlist=["CentroDeCosto"]).CentroDeCosto
    CentroDeCosto.objects.get_or_create(
        slug=gastos.CENTRO_SLUG, defaults={"nombre": "Insumos de proyecto"})
    prov = Proveedor.objects.create(razon_social="Simil Cuero", activo=True)
    p = _proyecto_con_gastos(proyecto_factory, prov)
    r = client.get(f"/proyectos/{p.pk}/pago-proveedor/{prov.pk}/registrar",
                   HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Registrar pago" in html
    assert "3 conceptos" in html
    assert "Simil Cuero" in html


def test_recuadro_del_proyecto_muestra_un_renglon_por_proveedor(
        client, usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import Proveedor

    _login(client, usuario_factory)
    prov = Proveedor.objects.create(razon_social="Simil Cuero", activo=True)
    p = _proyecto_con_gastos(proyecto_factory, prov)
    html = client.get(f"/proyectos/{p.pk}/").content.decode()
    assert "1 proveedor por pagar · 3 conceptos sin registrar" in html
    assert f"/proyectos/{p.pk}/pago-proveedor/{prov.pk}/registrar" in html
