"""Ronda del 2026-07-26 (feedback de Oscar).

- Foto del producto DESDE la tarjeta del proyecto: si la línea tiene alias, la
  foto es de ese uso; si no, va al producto del catálogo.
- Los alias son parte de la base buscable de productos (lista y comboboxes).
- Historial de usos: columna del diferenciador + mini recuadro de la imagen.
- Vista previa del documento: hoja con márgenes + botón «Bajar PDF».
- PDF: tablas centradas, columnas numéricas a la derecha, línea gris clara y
  bloques que no se parten entre páginas.
- Nombre del PDF: COTIZACIÓN-[CLIENTE]-[PROYECTO]-[vN].
- Resumen: FACTURAS X EMITIR ignora los proyectos exentos; CUENTAS X COBRAR.
- Cliente: varias razones sociales (cada una con su RFC) y RFC ya no es único.
- El Chalán identifica al cliente por cualquier razón social o por su RFC.
- El slug se ve en la ficha del cliente y en la del proyecto.
- Facturas sin paginación.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _servicio(nombre="Playera", **kwargs):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción")
    return Servicio.objects.create(
        nombre=nombre, categoria=cat,
        precio_base=kwargs.pop("precio_base", Decimal("120.00")),
        costo=kwargs.pop("costo", Decimal("70.00")), **kwargs)


def _linea(proyecto, servicio, **kwargs):
    from apps.los_proyectos.models import ProyectoProducto
    return ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=servicio,
        cantidad=kwargs.pop("cantidad", 10), **kwargs)


# ── (1) Foto del producto desde la tarjeta del proyecto ──────────────────────

def test_el_destino_de_la_foto_lo_decide_el_alias(proyecto_factory):
    """Con alias la foto es del USO; sin alias, del producto del catálogo."""
    p = proyecto_factory()
    srv = _servicio()
    con_alias = _linea(p, srv, nombre_proyecto="TShirt Modelo Janet")
    sin_alias = _linea(p, srv)

    assert con_alias.imagen_destino == "uso"
    assert sin_alias.imagen_destino == "catalogo"


def test_la_foto_del_uso_gana_sobre_la_del_catalogo(proyecto_factory):
    p = proyecto_factory()
    srv = _servicio()
    srv.imagen_file_id = "del-catalogo"
    srv.save()
    linea = _linea(p, srv)

    # Sin foto propia hereda la del catálogo…
    assert linea.imagen_efectiva_file_id == "del-catalogo"
    assert linea.imagen_es_propia is False
    # …y con foto propia, manda la suya.
    linea.imagen_file_id = "de-este-uso"
    linea.save()
    assert linea.imagen_efectiva_file_id == "de-este-uso"
    assert linea.imagen_es_propia is True


def test_subir_foto_con_alias_la_guarda_en_el_uso(client, proyecto_factory,
                                                  usuario_factory, monkeypatch):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(creado_por=admin)
    srv = _servicio()
    linea = _linea(p, srv, nombre_proyecto="TShirt Modelo Janet")

    class _Res:
        ok = True
        error = ""
        data = {"id": "file-123", "webViewLink": "https://drive/x"}

    monkeypatch.setattr("lib.adjuntos.subir", lambda *a, **k: _Res())
    client.force_login(admin)
    r = client.post(
        reverse("proyectos-producto-imagen", args=[linea.pk]),
        {"imagen": SimpleUploadedFile("foto.png", b"png", content_type="image/png")},
    )
    assert r.status_code == 200
    assert r.json()["destino"] == "uso"
    linea.refresh_from_db()
    srv.refresh_from_db()
    assert linea.imagen_file_id == "file-123"
    assert srv.imagen_file_id == ""  # el catálogo no se tocó


def test_subir_foto_sin_alias_la_guarda_en_el_catalogo(client, proyecto_factory,
                                                       usuario_factory, monkeypatch):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(creado_por=admin)
    srv = _servicio()
    linea = _linea(p, srv)

    class _Res:
        ok = True
        error = ""
        data = {"id": "file-cat", "webViewLink": "https://drive/y"}

    monkeypatch.setattr("lib.adjuntos.subir", lambda *a, **k: _Res())
    client.force_login(admin)
    r = client.post(
        reverse("proyectos-producto-imagen", args=[linea.pk]),
        {"imagen": SimpleUploadedFile("foto.png", b"png", content_type="image/png")},
    )
    assert r.status_code == 200
    assert r.json()["destino"] == "catalogo"
    srv.refresh_from_db()
    assert srv.imagen_file_id == "file-cat"


def test_subir_foto_sin_permiso_de_proyecto_da_403(client, proyecto_factory,
                                                   usuario_factory):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse

    p = proyecto_factory()
    linea = _linea(p, _servicio())
    client.force_login(usuario_factory(rol="disenador"))
    r = client.post(
        reverse("proyectos-producto-imagen", args=[linea.pk]),
        {"imagen": SimpleUploadedFile("foto.png", b"png", content_type="image/png")},
    )
    assert r.status_code == 403


def test_el_proxy_de_imagen_solo_sirve_fotos_de_productos(client, usuario_factory):
    """El file_id debe pertenecer a un producto, un uso o una línea de
    cotización; cualquier otro archivo de Drive es 404 seco."""
    from django.urls import reverse
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.get(reverse("catalogo-imagen-producto", args=["archivo-ajeno"]))
    assert r.status_code == 404


# ── (2) Alias buscables ─────────────────────────────────────────────────────

def test_la_lista_de_productos_encuentra_por_alias(client, proyecto_factory,
                                                   usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    srv = _servicio(nombre="TShirt Oversize Color")
    _linea(proyecto_factory(), srv, nombre_proyecto="TShirt Modelo Janet")

    client.force_login(admin)
    html = client.get(reverse("catalogo-lista"), {"q": "Janet"}).content.decode()
    assert "TShirt Oversize Color" in html


def test_el_combobox_marca_los_alias_en_data_buscar(proyecto_factory):
    from apps.el_catalogo.widgets import mapa_alias
    from apps.los_proyectos.forms import ProyectoProductoForm

    srv = _servicio(nombre="TShirt Oversize Color")
    _linea(proyecto_factory(), srv, nombre_proyecto="TShirt Modelo Janet")

    alias = mapa_alias(usar_cache=False)
    assert alias[srv.pk] == ["TShirt Modelo Janet"]

    # El form real ya trae el widget buscable; el alias viaja en `data-buscar` y
    # el producto sigue apareciendo como opción (regresión: cambiar el widget sin
    # re-asignar el queryset dejaba el `<select>` vacío).
    html = str(ProyectoProductoForm()["servicio"])
    assert "TShirt Oversize Color" in html
    assert 'data-buscar="TShirt Modelo Janet"' in html


def test_el_chalan_encuentra_productos_por_alias(proyecto_factory, usuario_factory):
    from capacidades.lecturas import _h_buscar_catalogo

    srv = _servicio(nombre="TShirt Oversize Color")
    _linea(proyecto_factory(), srv, nombre_proyecto="TShirt Modelo Janet")

    res = _h_buscar_catalogo({"texto": "Janet"}, usuario_factory(rol="super_admin"))
    nombres = [p["nombre"] for p in res["productos"]]
    assert "TShirt Oversize Color" in nombres
    assert "TShirt Modelo Janet" in res["productos"][0]["tambien_llamado"]


# ── (3) Historial de usos ───────────────────────────────────────────────────

def test_el_historial_de_usos_muestra_diferenciador_e_imagen(client, proyecto_factory,
                                                             usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    srv = _servicio()
    _linea(proyecto_factory(), srv, nombre_proyecto="TShirt Modelo Janet")

    client.force_login(admin)
    html = client.get(reverse("catalogo-usos", args=[srv.pk])).content.decode()
    assert "Diferenciador" in html
    assert "TShirt Modelo Janet" in html
    # El mini recuadro de imagen es el mismo componente de pegar/subir.
    assert "data-img-slot" in html


# ── (4) Vista previa del documento ──────────────────────────────────────────

def _cotizacion(proyecto, autor, **kwargs):
    from apps.cotizaciones.models import Cotizacion
    return Cotizacion.objects.create(
        codigo=kwargs.pop("codigo", "COT-2026-9200"), cliente=proyecto.cliente,
        proyecto=proyecto, titulo=proyecto.nombre, estado="generada",
        version=kwargs.pop("version", 1), creado_por=autor,
        fecha_emision=dt.date(2026, 7, 26), **kwargs)


def _cot_con_linea(proyecto, autor, **kwargs):
    from apps.cotizaciones.models import CotizacionItem
    cot = _cotizacion(proyecto, autor, **kwargs)
    CotizacionItem.objects.create(
        cotizacion=cot, concepto="Gorras", descripcion="105 pz (3 colores)",
        cantidad=105, precio_unitario=Decimal("120.00"))
    return cot


def test_la_vista_previa_es_una_hoja_con_boton_de_bajar_pdf(client, proyecto_factory,
                                                            usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cot = _cot_con_linea(proyecto_factory(nombre="Ted Lasso"), admin)

    client.force_login(admin)
    html = client.get(reverse("cotizaciones:ver", args=[cot.pk])).content.decode()
    assert "lc-hoja" in html            # hoja carta con márgenes
    assert "Bajar PDF" in html
    assert reverse("cotizaciones:pdf", args=[cot.pk]) in html


def test_el_documento_que_va_a_google_no_lleva_el_envoltorio(proyecto_factory,
                                                             usuario_factory):
    from apps.cotizaciones.services import construir_html_pdf
    admin = usuario_factory(rol="super_admin")
    cot = _cot_con_linea(proyecto_factory(nombre="Ted Lasso"), admin)

    html = construir_html_pdf(cot)
    assert "lc-hoja" not in html
    assert "Bajar PDF" not in html


# ── (5) Ajustes al PDF ──────────────────────────────────────────────────────

def test_el_pdf_alinea_los_numeros_a_la_derecha_y_el_concepto_a_la_izquierda(
        proyecto_factory, usuario_factory):
    from apps.cotizaciones.services import construir_html_pdf
    admin = usuario_factory(rol="super_admin")
    cot = _cot_con_linea(proyecto_factory(nombre="Ted Lasso"), admin)
    cot.incluir_desglose = True
    cot.save()
    # LC 2026-08-04: con un solo producto la tabla del desglose ya no se imprime.
    from apps.cotizaciones.models import CotizacionItem
    CotizacionItem.objects.create(
        cotizacion=cot, orden=1, concepto="Bolsas", descripcion="50 pz",
        cantidad=50, precio_unitario=Decimal("90.00"))

    html = construir_html_pdf(cot)
    # Columnas numéricas a la derecha (montos + desglose = varias celdas).
    assert html.count("text-align:right") >= 6
    assert "text-align:left; font-style:italic;\">Gorras" in html
    # Línea gris clara, nunca negra.
    assert "border:1px solid #cccccc" in html
    assert "border:1px solid #000000" not in html
    # Ni el bloque del producto ni el desglose se parten entre páginas.
    assert html.count("page-break-inside:avoid") >= 3


def test_el_pdf_centra_las_tablas_con_columnas_vacias(proyecto_factory, usuario_factory):
    """Docs ignora `align`/`margin:auto` en tablas: el centrado se logra con una
    columna vacía a cada lado dentro de la misma tabla."""
    from apps.cotizaciones.services import construir_html_pdf
    admin = usuario_factory(rol="super_admin")
    cot = _cot_con_linea(proyecto_factory(nombre="Ted Lasso"), admin)

    html = construir_html_pdf(cot)
    assert html.count('style="border:none; width:11%;"') >= 1


def test_la_foto_congelada_de_la_linea_manda_en_el_documento(proyecto_factory,
                                                             usuario_factory):
    from apps.cotizaciones.models import CotizacionItem
    admin = usuario_factory(rol="super_admin")
    srv = _servicio()
    srv.imagen_file_id = "del-catalogo"
    srv.save()
    cot = _cotizacion(proyecto_factory(nombre="Ted Lasso"), admin)
    it = CotizacionItem.objects.create(
        cotizacion=cot, servicio=srv, concepto="Gorras", cantidad=1,
        precio_unitario=Decimal("100.00"), imagen_file_id="congelada")

    assert it.imagen_visible_file_id == "congelada"
    it.imagen_file_id = ""
    assert it.imagen_visible_file_id == "del-catalogo"


def test_generar_version_congela_la_foto_del_uso(proyecto_factory, usuario_factory):
    from apps.cotizaciones import services
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Ted Lasso")
    srv = _servicio()
    srv.imagen_file_id = "del-catalogo"
    srv.save()
    _linea(p, srv, nombre_proyecto="Janet", imagen_file_id="del-uso")

    cot = services.generar_desde_proyecto(p, admin)
    assert cot.items.first().imagen_file_id == "del-uso"


# ── (6) Nombre del archivo ──────────────────────────────────────────────────

def test_el_nombre_del_pdf_sigue_la_convencion_de_lc(proyecto_factory, usuario_factory,
                                                      cliente_factory):
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(razon_social="Optimist")
    p = proyecto_factory(cliente=cli, nombre="Ted Lasso")
    cot = _cotizacion(p, admin, version=2)

    # CLIENTE en mayúsculas · PROYECTO sin espacios · versión en minúsculas.
    assert cot.nombre_pdf == "COTIZACIÓN-OPTIMIST-TedLasso-v2"


# ── (7) Resumen de pendientes ───────────────────────────────────────────────

def _seccion(secciones, titulo):
    return next((s for s in secciones if s["titulo"] == titulo), None)


def test_facturas_por_emitir_ignora_los_proyectos_exentos(proyecto_factory,
                                                          usuario_factory):
    from apps.taller_home.pendientes import secciones_pendientes
    admin = usuario_factory(rol="super_admin")
    proyecto_factory(nombre="Con IVA", estado="entregado", regimen_fiscal="honorarios")
    proyecto_factory(nombre="Sin IVA", estado="entregado", regimen_fiscal="exento")

    lineas = "\n".join(_seccion(secciones_pendientes(admin), "FACTURAS X EMITIR")["lineas"])
    assert "Con IVA" in lineas
    assert "Sin IVA" not in lineas


def test_cuentas_por_cobrar_incluye_proyectos_sin_factura(proyecto_factory,
                                                          usuario_factory):
    """Ya no son sólo facturas: entra todo lo que el CxC unificado reporte."""
    from apps.taller_home.pendientes import secciones_pendientes
    admin = usuario_factory(rol="super_admin")
    # El CxC legacy de un proyecto es lo facturado menos lo cobrado.
    p = proyecto_factory(nombre="Ted Lasso", estado="entregado",
                         monto_facturado=Decimal("5000.00"))

    seccion = _seccion(secciones_pendientes(admin), "CUENTAS X COBRAR")
    assert seccion is not None
    assert any(p.nombre in linea for linea in seccion["lineas"])


# ── (8) Razones sociales del cliente ────────────────────────────────────────

def test_el_cliente_puede_tener_varias_razones_sociales(cliente_factory):
    from apps.la_cartera.models import ClienteRazonSocial
    cli = cliente_factory(razon_social="GRUPO LAZANTO")
    ClienteRazonSocial.objects.create(
        cliente=cli, razon_social="LAZANTO COMERCIAL", rfc="LAC010101AAA", principal=True)
    ClienteRazonSocial.objects.create(
        cliente=cli, razon_social="LAZANTO SERVICIOS", rfc="LAS010101BBB")

    assert cli.razones_sociales.count() == 2
    assert cli.razon_social_principal.razon_social == "LAZANTO COMERCIAL"


def test_dos_clientes_pueden_compartir_rfc(cliente_factory):
    """Grupo Lazanto factura para Cueva y para Kari Kari: el RFC ya no es único."""
    cliente_factory(razon_social="CUEVA", rfc="GLA010101AAA")
    otro = cliente_factory(razon_social="KARI KARI", rfc="GLA010101AAA")
    assert otro.pk  # sin IntegrityError


def test_el_formset_espeja_la_razon_principal(client, cliente_factory, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(razon_social="OPTIMIST")
    client.force_login(admin)
    r = client.post(f"/cartera/{cli.pk}/editar", {
        "razon_social": "OPTIMIST", "estado": "activo", "direccion": "", "notas": "",
        "contactos-TOTAL_FORMS": "0", "contactos-INITIAL_FORMS": "0",
        "contactos-MIN_NUM_FORMS": "0", "contactos-MAX_NUM_FORMS": "1000",
        "razones_sociales-TOTAL_FORMS": "1", "razones_sociales-INITIAL_FORMS": "0",
        "razones_sociales-MIN_NUM_FORMS": "0", "razones_sociales-MAX_NUM_FORMS": "1000",
        "razones_sociales-0-razon_social": "marketing veintitres grados",
        "razones_sociales-0-rfc": "mvg010101aaa",
    }, follow=True)
    assert r.status_code == 200
    cli.refresh_from_db()
    # La razón social se guarda en mayúsculas y se espeja a los campos legacy.
    assert cli.razones_sociales.count() == 1
    assert cli.razon_social_fiscal == "MARKETING VEINTITRES GRADOS"
    assert cli.rfc == "MVG010101AAA"


def test_la_ficha_del_cliente_lista_las_razones_sociales(client, cliente_factory,
                                                          usuario_factory):
    from apps.la_cartera.models import ClienteRazonSocial
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(razon_social="OPTIMIST")
    ClienteRazonSocial.objects.create(
        cliente=cli, razon_social="MARKETING VEINTITRES GRADOS", rfc="MVG010101AAA",
        principal=True)

    client.force_login(admin)
    html = client.get(reverse("cartera-detalle", args=[cli.pk])).content.decode()
    assert "MARKETING VEINTITRES GRADOS" in html
    assert "MVG010101AAA" in html


def test_la_lista_de_clientes_busca_por_cualquier_razon_social(client, cliente_factory,
                                                               usuario_factory):
    from apps.la_cartera.models import ClienteRazonSocial
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(razon_social="OPTIMIST")
    ClienteRazonSocial.objects.create(
        cliente=cli, razon_social="MARKETING VEINTITRES GRADOS", rfc="MVG010101AAA")

    client.force_login(admin)
    html = client.get(reverse("cartera-lista"), {"q": "VEINTITRES"}).content.decode()
    assert "OPTIMIST" in html


# ── (9) El Chalán identifica al cliente ─────────────────────────────────────

def test_el_chalan_identifica_al_cliente_por_su_razon_social(cliente_factory):
    from apps.el_dictado.ejecutores.basicos import _cliente_por_razon_social
    from apps.la_cartera.models import ClienteRazonSocial

    cli = cliente_factory(razon_social="OPTIMIST")
    ClienteRazonSocial.objects.create(
        cliente=cli, razon_social="MARKETING VEINTITRES GRADOS", rfc="MVG010101AAA",
        principal=True)

    # Exacta, con «S.A. de C.V.», con acentos y con puntuación: todas ligan.
    for texto in (
        "MARKETING VEINTITRES GRADOS",
        "Marketing Veintitrés Grados, S.A. de C.V.",
        "marketing veintitres grados sa de cv",
        "MVG010101AAA",
    ):
        assert _cliente_por_razon_social(texto) == cli, texto


def test_el_chalan_no_adivina_cuando_hay_dos_candidatos(cliente_factory):
    from apps.el_dictado.ejecutores.basicos import _cliente_por_razon_social
    cliente_factory(razon_social="GRUPO LAZANTO CUEVA")
    cliente_factory(razon_social="GRUPO LAZANTO KARI KARI")
    assert _cliente_por_razon_social("GRUPO LAZANTO") is None


def test_el_ejecutor_de_factura_liga_por_razon_social(cliente_factory, usuario_factory):
    from apps.el_dictado.ejecutores.basicos import _resolver_cliente
    from apps.la_cartera.models import ClienteRazonSocial

    cli = cliente_factory(razon_social="OPTIMIST")
    ClienteRazonSocial.objects.create(
        cliente=cli, razon_social="MARKETING VEINTITRES GRADOS", principal=True)
    assert _resolver_cliente("Marketing Veintitres Grados S.A. de C.V.") == cli


# ── (10) Slug visible ───────────────────────────────────────────────────────

def test_el_slug_se_ve_en_la_ficha_del_cliente_y_del_proyecto(client, proyecto_factory,
                                                              usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Ted Lasso", creado_por=admin)

    client.force_login(admin)
    html_p = client.get(reverse("proyectos-detalle", args=[p.pk])).content.decode()
    assert f"#{p.slug}" in html_p

    html_c = client.get(reverse("cartera-detalle", args=[p.cliente.pk])).content.decode()
    assert f"${p.cliente.slug}" in html_c


# ── (11) Facturas sin paginación ────────────────────────────────────────────

def test_la_lista_de_facturas_no_pagina(client, usuario_factory, cliente_factory):
    from apps.facturacion.models import Factura
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory()
    for n in range(30):
        Factura.objects.create(
            cliente=cli, estado="borrador", concepto=f"Servicio {n}",
            fecha_emision=dt.date(2026, 7, 26), fecha_vencimiento=dt.date(2026, 8, 26))

    client.force_login(admin)
    r = client.get(reverse("facturacion:lista"))
    assert r.status_code == 200
    assert r.context["page_obj"] is None
    assert len(r.context["facturas"]) == 30
