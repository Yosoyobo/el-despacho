"""Segunda ronda de ajustes de Oscar sobre el deploy 2026.07.28/29.

Cubre: el documento de la cotización (título editable, hueco dinámico de las
notas, tablas sin líneas), la caché de imágenes que arregla el hueco de la foto
en el PDF, la ficha del proveedor (historial completo + «¿Qué surte?» arriba),
la capacidad `buscar_proveedor` de El Chalán, el registro de facturas dictando
la razón social fiscal y el monto con o sin impuestos, y los estados ocultos
que ya no salen como filtro.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def entorno(usuario_factory, cliente_factory, proyecto_factory):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="Producción", defaults={"orden": 10})
    prov = Proveedor.objects.create(razon_social="Simil Cuero Plymouth")
    srv = Servicio.objects.create(
        nombre="Mandil de mezclilla", precio_base="510", costo="180", categoria=cat)
    srv.proveedores.add(prov)
    cli = cliente_factory(razon_social="Optimist", razon_social_fiscal="MARKETING VEINTITRES GRADOS")
    proy = proyecto_factory(nombre="Marriott Bonvoy", cliente=cli, creado_por=admin)
    cot = Cotizacion.objects.create(
        cliente=cli, proyecto=proy, titulo="Marriott Bonvoy", version=1, creado_por=admin)
    CotizacionItem.objects.create(
        cotizacion=cot, servicio=srv, concepto="Mandil de mezclilla",
        descripcion="35 pz\nBordado a 1 tinta", cantidad=35, precio_unitario="510")
    return {"admin": admin, "cli": cli, "proy": proy, "cot": cot,
            "srv": srv, "prov": prov, "cat": cat}


# ── El documento (PDF) ────────────────────────────────────────────────────

class TestDocumento:

    def test_titulo_automatico_sale_del_proyecto(self, entorno):
        assert entorno["cot"].titulo_documento == (
            "Producción de elementos para proyecto 'Marriott Bonvoy'")

    def test_titulo_manual_le_gana_al_automatico(self, entorno):
        cot = entorno["cot"]
        cot.titulo_documento_manual = "Propuesta de uniformes 2026"
        cot.save(update_fields=["titulo_documento_manual"])
        assert cot.titulo_documento == "Propuesta de uniformes 2026"
        # …y el automático sigue disponible para mostrarlo como sugerencia.
        assert cot.titulo_documento_auto.startswith("Producción de elementos")

    def test_titulo_manual_en_blanco_vuelve_al_automatico(self, entorno):
        cot = entorno["cot"]
        cot.titulo_documento_manual = "   "
        assert cot.titulo_documento == cot.titulo_documento_auto

    def test_endpoint_guarda_el_titulo(self, client, entorno):
        client.force_login(entorno["admin"])
        r = client.post(
            f"/cotizaciones/{entorno['cot'].pk}/documento/",
            {"campo": "titulo_documento_manual", "valor_titulo_documento_manual": "Uniformes Marriott"},
        )
        # LC 2026-07-26 (ronda 3): el endpoint devuelve el recuadro «Documento»
        # repintado; el control del título lo ignora con `hx-swap="none"`.
        assert r.status_code == 200
        entorno["cot"].refresh_from_db()
        assert entorno["cot"].titulo_documento == "Uniformes Marriott"

    def test_la_version_siguiente_hereda_el_titulo(self, entorno):
        from apps.cotizaciones import services
        cot = entorno["cot"]
        cot.titulo_documento_manual = "Uniformes Marriott"
        cot.save(update_fields=["titulo_documento_manual"])
        v2 = services.generar_desde_proyecto(entorno["proy"], entorno["admin"])
        assert v2.titulo_documento_manual == "Uniformes Marriott"

    def test_las_tablas_de_layout_no_llevan_lineas(self, entorno):
        from apps.cotizaciones import services
        html = services.construir_html_pdf(entorno["cot"])
        # Google Docs pinta bordes negros si el HTML no los apaga a la brava.
        assert 'border="0"' in html
        assert "border:none" in html
        # El encabezado (fecha/logo/cliente) va sin líneas; las tablas de
        # conceptos SÍ llevan recuadro desde la tercera ronda (2026-07-25).
        encabezado = html.split("<u>", 1)[0]
        assert "border:1px solid" not in encabezado

    def test_la_tabla_de_montos_va_centrada_y_con_encabezados_cortos(self, entorno):
        from apps.cotizaciones import services
        html = services.construir_html_pdf(entorno["cot"])
        assert 'align="center"' in html
        assert "P. Unitario" in html
        assert "Precio Unitario" not in html.split("Desglose de Elementos")[0]

    def test_el_logo_va_en_un_parrafo_centrado(self, entorno):
        from apps.cotizaciones import services
        html = services.construir_html_pdf(entorno["cot"])
        assert '<p align="center"' in html

    def test_las_notas_ya_no_llevan_linea_divisoria(self, entorno):
        from apps.cotizaciones import services
        html = services.construir_html_pdf(entorno["cot"])
        assert "border-top:1px solid #d9d9d9" not in html
        assert "page-break-inside:avoid" in html

    def test_el_hueco_de_las_notas_es_dinamico(self, entorno):
        """Un documento cortito deja hueco; uno largo ya no estira nada."""
        from apps.cotizaciones import services
        from apps.cotizaciones.models import CotizacionItem
        cot = entorno["cot"]
        hueco_corto = services._espacio_antes_de_notas(
            cot, [], [], ["nota"] * 8)
        assert hueco_corto > 0

        for i in range(40):
            CotizacionItem.objects.create(
                cotizacion=cot, concepto=f"Producto {i}",
                descripcion="línea\n" * 6, cantidad=1, precio_unitario="100")
        items = list(cot.items.all())
        filas = [{"it": it, "imagen": ""} for it in items]
        hueco_largo = services._espacio_antes_de_notas(cot, filas, items, ["nota"] * 8)
        assert hueco_largo < hueco_corto
        assert hueco_largo >= 0


# ── La foto del PDF (caché) ───────────────────────────────────────────────

class TestImagenPublica:

    def test_precalentar_deja_la_imagen_lista_para_servir(self, monkeypatch, entorno):
        from django.core.cache import cache

        from lib import imagen_publica
        cache.clear()
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
            b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        llamadas = {"n": 0}

        class _Drive:
            def descargar(self, file_id):
                llamadas["n"] += 1
                return png, "image/png", "foto.png"

        monkeypatch.setattr("lib.google_drive.drive", _Drive())
        assert imagen_publica.precalentar("archivo-1") is True
        assert imagen_publica.desde_cache("archivo-1") is not None
        # Segunda vez no vuelve a pegarle a Drive.
        imagen_publica.precalentar("archivo-1")
        assert llamadas["n"] == 1

    def test_precalentar_no_truena_si_drive_esta_caido(self, monkeypatch):
        from lib import imagen_publica

        class _Drive:
            def descargar(self, file_id):
                raise RuntimeError("Drive caído")

        monkeypatch.setattr("lib.google_drive.drive", _Drive())
        assert imagen_publica.precalentar("archivo-roto") is False

    def test_generar_pdf_precalienta_antes_de_llamar_a_google(self, monkeypatch, entorno):
        from apps.cotizaciones import services
        entorno["srv"].imagen_file_id = "foto-mandil"
        entorno["srv"].save(update_fields=["imagen_file_id"])
        orden = []
        monkeypatch.setattr(
            "lib.imagen_publica.precalentar",
            lambda fid: orden.append(("precalienta", fid)) or True)

        class _Res:
            ok = False
            error = "Drive no configurado"
            pdf_bytes = b""
            data: dict = {}

        monkeypatch.setattr(
            "lib.documentos.generar_pdf",
            lambda **kw: orden.append(("google", None)) or _Res())
        services.generar_pdf(entorno["cot"], entorno["admin"])
        assert orden == [("precalienta", "foto-mandil"), ("google", None)]


# ── Ficha del proveedor ───────────────────────────────────────────────────

class TestFichaProveedor:

    def test_muestra_los_proyectos_entregados(self, client, entorno):
        from apps.los_proyectos.models import ProyectoProducto
        proy = entorno["proy"]
        ProyectoProducto.objects.create(
            proyecto=proy, servicio=entorno["srv"], proveedor=entorno["prov"],
            cantidad=35, incluir_en_calculo=True)
        proy.estado = "entregado"
        proy.save(update_fields=["estado"])
        client.force_login(entorno["admin"])
        r = client.get(f"/catalogo/proveedores/{entorno['prov'].pk}/")
        assert r.status_code == 200
        assert "Marriott Bonvoy" in r.content.decode()

    def test_que_surte_vive_en_la_columna_grande(self, client, entorno):
        client.force_login(entorno["admin"])
        html = client.get(f"/catalogo/proveedores/{entorno['prov'].pk}/").content.decode()
        # Va antes que los datos de contacto, que son los que viven en el sidebar.
        assert 0 < html.index("¿Qué surte?") < html.index("Datos de contacto")
        # Y el bloque de Estado ya no vive dentro del form de autoguardado.
        assert html.count('id="form-proveedor"') == 1
        assert html.index("Eliminar permanentemente") > html.index("</form>")


# ── El Chalán: buscar_proveedor ───────────────────────────────────────────

class TestBuscarProveedor:

    def test_devuelve_ficha_con_productos_y_proyectos(self, entorno):
        from apps.los_proyectos.models import ProyectoProducto

        from capacidades import ejecutar
        ProyectoProducto.objects.create(
            proyecto=entorno["proy"], servicio=entorno["srv"],
            proveedor=entorno["prov"], cantidad=35, incluir_en_calculo=True)
        r = ejecutar("buscar_proveedor", {"nombre": "simil cuero"}, entorno["admin"])
        assert r["razon_social"] == "Simil Cuero Plymouth"
        assert any(p["producto"] == "Mandil de mezclilla" for p in r["surte"])
        assert any(p["codigo"] == entorno["proy"].codigo for p in r["proyectos_activos"])

    def test_incluye_deudas_y_pagos_con_permiso_de_finanzas(self, entorno):
        from apps.los_proyectos.models import ProyectoProducto

        from capacidades import ejecutar
        ProyectoProducto.objects.create(
            proyecto=entorno["proy"], servicio=entorno["srv"],
            proveedor=entorno["prov"], cantidad=10, costo_unitario="100",
            incluir_en_calculo=True)
        r = ejecutar("buscar_proveedor", {"nombre": "Simil Cuero Plymouth"}, entorno["admin"])
        assert "dinero" in r
        assert r["dinero"]["deuda_comprometida_en_proyectos"] > 0

    def test_sin_permiso_de_finanzas_no_expone_el_dinero(self, entorno, usuario_factory):
        """Defensa en profundidad: la capacidad se gatea con el Catálogo, pero
        la deuda y los pagos son otra cosa y llevan su propio candado."""
        from capacidades.lecturas import _h_buscar_proveedor
        disenador = usuario_factory(rol="disenador")
        r = _h_buscar_proveedor({"nombre": "Simil Cuero Plymouth"}, disenador)
        assert r["razon_social"] == "Simil Cuero Plymouth"
        assert "dinero" not in r

    def test_proveedor_inexistente_responde_claro(self, entorno):
        from capacidades import ejecutar
        r = ejecutar("buscar_proveedor", {"nombre": "Nadie SA"}, entorno["admin"])
        assert r["error"] == "no_encontrado"

    def test_esta_en_el_catalogo_visible_de_consultas(self):
        from lib.dictado_catalogo import CONSULTAS_CHAT
        assert any(c["nombre"] == "buscar_proveedor" for c in CONSULTAS_CHAT)


# ── El Chalán: registrar facturas ─────────────────────────────────────────

class TestFacturaDictada:

    def _accion(self, payload):
        class _Accion:
            def __init__(self, payload):
                self.payload = payload
                self.entidad_tipo = ""
                self.entidad_id = None
        return _Accion(payload)

    def test_resuelve_al_cliente_por_su_razon_social_fiscal(self, entorno):
        from apps.el_dictado.ejecutores.basicos import _resolver_cliente
        c = _resolver_cliente("marketing veintitres grados")
        assert c.pk == entorno["cli"].pk

    def test_razon_social_ambigua_no_se_adivina(self, entorno, cliente_factory):
        from apps.el_dictado.ejecutores.basicos import _resolver_cliente
        cliente_factory(razon_social="Optimist Norte")
        with pytest.raises(ValueError):
            _resolver_cliente("optimis")

    def test_registra_la_factura_con_monto_final(self, entorno):
        from apps.el_dictado.ejecutores.avanzados import crear_factura
        from apps.facturacion.models import Factura
        accion = self._accion({
            "cliente_slug": "MARKETING VEINTITRES GRADOS",
            "concepto": 'Bordado de Mandiles Proyecto "Marriott Bonvoy"',
            "monto_total": "2341.87",
            "fecha_emision": "2026-04-15",
            "folio": "F-106",
        })
        crear_factura(accion, entorno["admin"])
        fac = Factura.objects.get(pk=accion.entidad_id)
        assert fac.cliente_id == entorno["cli"].pk
        assert fac.concepto.startswith("Bordado de Mandiles")
        assert fac.fecha_emision == date(2026, 4, 15)
        assert fac.folio == "F106"
        assert fac.estado == "borrador"
        # El importe dictado ES el total del documento, ya con impuestos.
        assert fac.calcular_totales()["total"] == Decimal("2341.87")

    def test_monto_base_le_suma_los_impuestos_encima(self, entorno):
        from apps.el_dictado.ejecutores.avanzados import crear_factura
        from apps.facturacion.models import Factura

        from ajustes.models.tasa import TasaImpositiva
        TasaImpositiva.objects.create(
            nombre="IVA 16%", tipo="traslado", porcentaje="16", aplicable_default=True)
        accion = self._accion({
            "cliente_slug": "Optimist",
            "concepto": "Bordado de mandiles",
            "monto_base": "1000",
        })
        crear_factura(accion, entorno["admin"])
        fac = Factura.objects.get(pk=accion.entidad_id)
        totales = fac.calcular_totales()
        assert totales["subtotal_items"] == Decimal("1000.00")
        # Desde 2026-07-25 la factura dictada nace en «IVA y Retenciones»
        # (default del despacho): 1000 + IVA 160 − ISR 12.50 − ret. IVA 106.67.
        assert fac.regimen_fiscal == "honorarios"
        assert totales["total"] == Decimal("1040.83")

    def test_sin_monto_ni_items_pide_el_dato(self, entorno):
        from apps.el_dictado.ejecutores.avanzados import crear_factura
        accion = self._accion({"cliente_slug": "Optimist", "concepto": "Algo"})
        with pytest.raises(ValueError, match="monto"):
            crear_factura(accion, entorno["admin"])

    def test_folio_repetido_avisa_en_vez_de_reventar(self, entorno):
        from apps.el_dictado.ejecutores.avanzados import crear_factura
        base = {
            "cliente_slug": "Optimist", "concepto": "Bordado",
            "monto_total": "1000", "folio": "F-500",
        }
        crear_factura(self._accion(dict(base)), entorno["admin"])
        with pytest.raises(ValueError, match="F500"):
            crear_factura(self._accion(dict(base)), entorno["admin"])


# ── Estados ocultos fuera de los filtros ──────────────────────────────────

class TestEstadosOcultos:

    def test_la_pastilla_de_un_estado_oculto_desaparece(self, client, entorno):
        from apps.cotizaciones.models import EstadoCotizacion
        from apps.cotizaciones.models.estado_cotizacion import invalidar_cache_estados_cot
        from apps.cotizaciones.views import _pills_estados
        client.force_login(entorno["admin"])
        assert "enviada" in {p["slug"] for p in _pills_estados()}
        # …y sale renderizada en la página.
        html = client.get("/cotizaciones/").content.decode()
        assert "?estado=enviada" in html

        EstadoCotizacion.objects.filter(slug="enviada").update(activo=False)
        invalidar_cache_estados_cot()
        slugs = {p["slug"] for p in _pills_estados()}
        assert "enviada" not in slugs
        assert "aprobada" in slugs  # las demás siguen ahí
        assert "?estado=enviada" not in client.get("/cotizaciones/").content.decode()

    def test_los_estados_legacy_siempre_se_ofrecen(self, entorno):
        from apps.cotizaciones.views import _pills_estados
        slugs = {p["slug"] for p in _pills_estados()}
        assert {"borrador", "rechazada", "anulada"} <= slugs

    def test_proyectos_no_ofrece_un_estado_oculto(self, entorno):
        from apps.los_proyectos.models import EstadoProyecto
        from apps.los_proyectos.templatetags.proyectos_extras import invalidar_mapa_estados
        from apps.los_proyectos.views import _estados_para_filtro
        EstadoProyecto.objects.filter(slug="en_pausa").update(activo=False)
        invalidar_mapa_estados()
        slugs = {s for s, _ in _estados_para_filtro()}
        assert "en_pausa" not in slugs
        assert "por_cotizar" in slugs
