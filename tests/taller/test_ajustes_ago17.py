"""Escalas de volumen del producto + márgenes y pie del documento.

LC 2026-08-17 (Oscar, con los renders `b-render-tarjeta` y
`d-render-cotizacionespdf`). Dos entregas en un deploy:

**a/b — Escalas de volumen.** Un mismo producto se cotiza a varias cantidades y
el cliente escoge. La Opción A es la fila principal de la tarjeta; cada escala es
una alternativa B, C… El radio dice cuál calcula el dinero (una sola, con
constraint en la base) y el ojo si se imprime. Un campo vacío HEREDA de la Opción
A; un 0 escrito es un cero de verdad.

**c/d — El documento.** El margen superior baja a media pulgada (el encabezado
sube como en el formato de referencia), el inferior a 0.6" (+10% de área
imprimible), el logotipo crece 5% y el pie lleva un «1/1» anclado que no le quita
espacio al contenido.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

TPL_CARD = Path("el-taller/templates/proyectos/_producto_card.html")
TPL_ESCALA = Path("el-taller/templates/proyectos/_escala_fila.html")
TPL_JS = Path("el-taller/templates/proyectos/_form_productos_js.html")
TPL_PDF = Path("el-taller/templates/cotizaciones/pdf.html")

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
        nombre="Tote Bag", precio_base="195", costo="80", categoria=cat)
    return {"cat": cat, "prov": prov, "srv": srv}


@pytest.fixture
def entorno(usuario_factory, proyecto_factory, catalogo):
    """Un proyecto con una línea de 70 pz a 195, con impresión por pieza."""
    from apps.los_proyectos.models import ProyectoProducto, ProyectoProductoProceso
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Shopping Energy", creado_por=admin)
    linea = ProyectoProducto.objects.create(
        proyecto=p, servicio=catalogo["srv"], proveedor=catalogo["prov"],
        cantidad=70, merma=0,
        precio_unitario=Decimal("195.00"), costo_unitario=Decimal("80.00"),
        incluir_en_calculo=True,
    )
    ProyectoProductoProceso.objects.create(
        producto=linea, tipo="impresion", proveedor=catalogo["prov"],
        costo=Decimal("10.00"), por_pieza=True, orden=0)
    return {"admin": admin, "p": p, "linea": linea, **catalogo}


def _escala(linea, **kw):
    from apps.los_proyectos.models import ProyectoProductoEscala
    datos = {"cantidad": 100, "orden": 0}
    datos.update(kw)
    return ProyectoProductoEscala.objects.create(producto=linea, **datos)


# ══════════════════════════════════════════════════════════════════════════════
# a/b — Escalas de volumen: el modelo
# ══════════════════════════════════════════════════════════════════════════════


def test_sin_escalas_nada_cambia(entorno):
    """Regresión: una línea sin escalas se calcula exactamente como antes."""
    pp = entorno["linea"]
    assert pp.escala_activa is None
    assert pp.cantidad_efectiva == 70
    assert pp.merma_efectiva == 0
    assert pp.precio_efectivo == Decimal("195.00")
    assert pp.costo_efectivo == Decimal("80.00")
    assert pp.subtotal == Decimal("13650.00")            # 70 × 195
    # 70 × 80 de producto + 70 × 10 de impresión.
    assert pp.costo_total_con_procesos == Decimal("6300.00")


def test_la_escala_activa_manda_el_dinero_del_proyecto(entorno):
    """El monto, el costo y el margen del proyecto salen de la opción marcada."""
    pp = entorno["linea"]
    _escala(pp, cantidad=100, precio_unitario=Decimal("175.00"), activa=True)
    pp.refresh_from_db()
    assert pp.cantidad_efectiva == 100
    assert pp.precio_efectivo == Decimal("175.00")
    assert pp.subtotal == Decimal("17500.00")           # 100 × 175
    # Costo: hereda el costo unitario (80) y la impresión por pieza (10) de A.
    assert pp.costo_total_con_procesos == Decimal("9000.00")
    assert entorno["p"].monto_calculado == Decimal("17500.00")


def test_vacio_hereda_pero_el_cero_escrito_es_cero(entorno):
    """La diferencia que NO puede colapsarse: vacío = heredar, 0 = gratis."""
    pp = entorno["linea"]
    hereda = _escala(pp, cantidad=100, activa=True)      # todo vacío
    assert hereda.precio_efectivo == Decimal("195.00")   # el de la Opción A
    assert hereda.costo_efectivo == Decimal("80.00")
    # Impresión heredada: 10 por pieza × 100 piezas.
    assert hereda.costo_procesos == Decimal("1000.00")

    hereda.impresion_costo = Decimal("0.00")             # cero EXPLÍCITO
    hereda.save()
    assert hereda.costo_procesos == Decimal("0.00")


def test_la_escala_suma_impresion_propia_operativos_heredados_y_extras(entorno):
    """El costo de una escala: impresión propia (pisa la de A), los gastos
    operativos de A recalculados con SUS piezas, y sus costos extra."""
    from apps.los_proyectos.models import ProyectoProductoProceso
    pp = entorno["linea"]
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="operativo", descripcion="Positivos",
        costo=Decimal("150.00"), por_pieza=False, orden=1)
    e = _escala(
        pp, cantidad=100, merma=5, activa=True,
        impresion_costo=Decimal("8.00"), impresion_por_pieza=True,
        extras_json=[{"costo": "35.00", "costo_expr": "", "por_pieza": False}],
    )
    # 8 × 105 piezas + 150 fijos + 35 extra fijos.
    assert e.costo_procesos == Decimal("1025.00")
    assert e.piezas == 105


def test_una_sola_escala_activa_por_producto(entorno):
    """La regla vive en la base, no sólo en el JS."""
    from django.db import IntegrityError, transaction
    pp = entorno["linea"]
    _escala(pp, cantidad=100, activa=True, orden=0)
    with pytest.raises(IntegrityError), transaction.atomic():
        _escala(pp, cantidad=200, activa=True, orden=1)


def test_las_escalas_se_llaman_b_c_d(entorno):
    pp = entorno["linea"]
    assert _escala(pp, orden=0).letra == "B"
    assert _escala(pp, orden=1, cantidad=200).letra == "C"
    assert _escala(pp, orden=2, cantidad=300).letra == "D"


def test_opciones_del_documento_activa_primero_y_nunca_vacio(entorno):
    """La activa carga el concepto y el total, así que va al frente. Y si
    apagaron todos los ojos, el documento no se queda sin renglón."""
    pp = entorno["linea"]
    b = _escala(pp, cantidad=100, activa=True, orden=0)
    c = _escala(pp, cantidad=200, orden=1)
    pp.refresh_from_db()
    opciones = pp.opciones_documento()
    assert opciones[0] == b                    # la activa primero
    assert None in opciones                    # la Opción A como alternativa
    assert c in opciones

    pp.visible_pdf = False
    pp.save()
    c.visible_pdf = False
    c.save()
    b.visible_pdf = False
    b.save()
    pp.refresh_from_db()
    assert pp.opciones_documento() == [b]      # queda la que manda


# ══════════════════════════════════════════════════════════════════════════════
# a/b — El sanitizador (las reglas se imponen en el servidor)
# ══════════════════════════════════════════════════════════════════════════════


def test_normalizadas_una_sola_activa_gana_la_primera():
    from apps.los_proyectos.services_procesos import escalas_normalizadas
    crudo = json.dumps([
        {"cantidad": 100, "activa": True},
        {"cantidad": 200, "activa": True},
    ])
    salida = escalas_normalizadas(crudo)
    assert [e["activa"] for e in salida] == [True, False]


def test_normalizadas_vacio_es_none_y_cero_es_cero():
    from apps.los_proyectos.services_procesos import escalas_normalizadas
    salida = escalas_normalizadas(json.dumps([
        {"cantidad": 100, "precio_unitario": "", "impresion_costo": "0"},
    ]))
    assert salida[0]["precio_unitario"] is None
    assert salida[0]["impresion_costo"] == Decimal("0.00")


def test_normalizadas_acepta_cuenta_escrita_en_el_costo():
    from apps.los_proyectos.services_procesos import escalas_normalizadas
    salida = escalas_normalizadas(json.dumps([
        {"cantidad": 100, "costo_unitario": "0", "costo_unitario_expr": "35+15+15"},
    ]))
    assert salida[0]["costo_unitario"] == Decimal("65.00")
    assert salida[0]["costo_unitario_expr"] == "35+15+15"


def test_normalizadas_ignora_la_fila_que_nunca_se_lleno():
    from apps.los_proyectos.services_procesos import escalas_normalizadas
    salida = escalas_normalizadas(json.dumps([
        {"cantidad": "", "precio_unitario": "", "costo_unitario": ""},
        {"cantidad": 200},
    ]))
    assert len(salida) == 1
    assert salida[0]["cantidad"] == 200


def test_normalizadas_json_invalido_no_toca_nada():
    from apps.los_proyectos.services_procesos import escalas_normalizadas
    assert escalas_normalizadas("{no soy json") is None
    assert escalas_normalizadas(None) is None
    assert escalas_normalizadas(json.dumps({"no": "lista"})) is None


def test_sincronizar_puede_mover_la_activa_sin_romper_el_constraint(entorno):
    """Pasar la activa de la B a la C: si no se apagaran todas primero, el
    constraint parcial rechazaría el momento intermedio."""
    from apps.los_proyectos.services_procesos import sincronizar_escalas
    pp = entorno["linea"]
    sincronizar_escalas(pp, json.dumps([
        {"cantidad": 100, "activa": True},
        {"cantidad": 200, "activa": False},
    ]))
    assert pp.escalas.get(cantidad=100).activa is True

    sincronizar_escalas(pp, json.dumps([
        {"cantidad": 100, "activa": False},
        {"cantidad": 200, "activa": True},
    ]))
    assert pp.escalas.get(cantidad=100).activa is False
    assert pp.escalas.get(cantidad=200).activa is True
    assert pp.escalas.count() == 2


def test_sincronizar_borra_las_que_ya_no_vienen(entorno):
    from apps.los_proyectos.services_procesos import sincronizar_escalas
    pp = entorno["linea"]
    sincronizar_escalas(pp, json.dumps([{"cantidad": 100}, {"cantidad": 200}]))
    assert pp.escalas.count() == 2
    sincronizar_escalas(pp, json.dumps([{"cantidad": 100}]))
    assert pp.escalas.count() == 1


# ══════════════════════════════════════════════════════════════════════════════
# a/b — La cotización: se imprimen, no suman
# ══════════════════════════════════════════════════════════════════════════════


def test_las_alternativas_se_congelan_como_informativas(entorno):
    from apps.cotizaciones import services
    pp = entorno["linea"]
    _escala(pp, cantidad=100, precio_unitario=Decimal("175.00"), activa=True)
    _escala(pp, cantidad=200, precio_unitario=Decimal("160.00"), orden=1)
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])

    principal = cot.items.filter(informativo=False, agrupado=False).get()
    assert principal.cantidad == Decimal("100.00")       # la ACTIVA
    assert principal.precio_unitario == Decimal("175.00")

    alternativas = list(cot.items.filter(informativo=True).order_by("orden"))
    cantidades = sorted(int(a.cantidad) for a in alternativas)
    assert cantidades == [70, 200]                       # la A y la C
    assert all(a.agrupado for a in alternativas)         # dentro de su bloque


def test_las_alternativas_no_suman_al_total(entorno):
    """El total refleja la opción activa, aunque el documento muestre las otras."""
    from apps.cotizaciones import services
    pp = entorno["linea"]
    _escala(pp, cantidad=100, precio_unitario=Decimal("175.00"), activa=True)
    _escala(pp, cantidad=200, precio_unitario=Decimal("160.00"), orden=1)
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    assert cot.calcular_totales()["subtotal_items"] == Decimal("17500.00")


def test_el_documento_imprime_las_alternativas_y_el_desglose_no(entorno):
    from apps.cotizaciones import services
    pp = entorno["linea"]
    from apps.los_proyectos.models import ProyectoProducto
    ProyectoProducto.objects.create(          # 2 productos ⇒ sale el desglose
        proyecto=entorno["p"], servicio=entorno["srv"], cantidad=5,
        precio_unitario=Decimal("100.00"), incluir_en_calculo=True)
    _escala(pp, cantidad=200, precio_unitario=Decimal("160.00"), orden=0)
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    cot.incluir_desglose = True
    cot.save(update_fields=["incluir_desglose"])

    html = services.construir_html_pdf(cot)
    # El renglón de la alternativa (200 × 160 = 32,000) va en la tabla de montos…
    assert "32,000" in html
    # …y el desglose sólo lista lo que se está comprando.
    desglose = html[html.index("Desglose de Elementos"):]
    assert "32,000" not in desglose


# ══════════════════════════════════════════════════════════════════════════════
# a/b — La foto por versión guarda TODO
# ══════════════════════════════════════════════════════════════════════════════


def test_la_version_congela_las_escalas_con_sus_nulos(entorno):
    from apps.cotizaciones import services
    pp = entorno["linea"]
    _escala(pp, cantidad=100, activa=True)   # hereda precio y costo de A
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    fila = cot.productos_version.get()
    assert len(fila.escalas_json) == 1
    guardada = fila.escalas_json[0]
    assert guardada["cantidad"] == 100
    assert guardada["activa"] is True
    # Heredaba: el nulo se conserva (si se aplanara a 0, la escala pasaría a
    # valer cero al repintar la pestaña).
    assert guardada["precio_unitario"] is None
    assert guardada["costo_unitario"] is None
    # Y la fila A conserva SUS valores, no los de la escala activa.
    assert fila.cantidad == 70
    assert fila.precio_unitario == Decimal("195.00")


def test_restaurar_una_version_repone_sus_escalas(entorno):
    from apps.cotizaciones import services
    from apps.los_proyectos import services_version
    pp = entorno["linea"]
    _escala(pp, cantidad=100, activa=True)
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    pp.escalas.all().delete()
    assert pp.escalas.count() == 0

    services_version.restaurar_en_edicion(cot, entorno["admin"])
    pp.refresh_from_db()
    assert pp.escalas.count() == 1
    assert pp.escalas.get().activa is True


# ══════════════════════════════════════════════════════════════════════════════
# a/b — La tarjeta y su JS
# ══════════════════════════════════════════════════════════════════════════════


def test_la_tarjeta_trae_el_radio_y_el_mas_de_la_escala():
    tpl = TPL_CARD.read_text(encoding="utf-8")
    # El radio de la Opción A, entre Producto y Cant. (columna `auto`).
    assert 'data-escala-radio="a"' in tpl
    # El ⊕ que agrega una escala, junto a la etiqueta «Cant.».
    assert "escala-add" in tpl
    assert tpl.index("escala-add") < tpl.index("{{ f.cantidad }}")
    # El ojo de la Opción A sólo aparece cuando hay escalas.
    assert "{% if f.escalas %}" in tpl
    # Y el bloque de escalas no ocupa su hueco cuando no hay ninguna.
    assert "[&:not(:has(.escala-fila))]:hidden" in tpl


def test_la_sub_fila_tiene_los_campos_del_render():
    tpl = TPL_ESCALA.read_text(encoding="utf-8")
    for clase in ("esc-radio", "esc-cant", "esc-merma", "esc-precio",
                  "esc-costo", "esc-imp", "esc-imp-pp", "esc-extra-add",
                  "esc-ojo", "esc-del"):
        assert clase in tpl, clase
    # Sin proveedor ni descripción propios: los hereda de la Opción A.
    assert "esc-proveedor" not in tpl
    # Los números van sin localizar o un input numérico no los entendería.
    assert "|unlocalize" in tpl
    # La letra de la opción, como en el render («CANTIDAD (B)»).
    assert "data-esc-letra" in tpl


def test_la_plantilla_js_coincide_con_el_partial():
    """El JS clona la sub-fila: si el partial gana un campo, la plantilla del JS
    también, o la escala nueva se serializa incompleta."""
    js = TPL_JS.read_text(encoding="utf-8")
    plantilla = js[js.index("function plantillaEscala"):js.index("function agregarEscala")]
    for clase in ("esc-radio", "esc-cant", "esc-merma", "esc-precio",
                  "esc-costo", "esc-imp", "esc-imp-pp", "esc-extras",
                  "esc-extra-add", "esc-ojo", "esc-del"):
        assert clase in plantilla, clase
    for marca in ("data-esc-letra", "data-esc-costo-total", "data-esc-costo-pp",
                  "data-esc-utilidad-pp", "data-esc-monto", "data-esc-utilidad",
                  "data-esc-margen"):
        assert marca in plantilla, marca


def test_el_js_manda_null_cuando_el_campo_va_vacio():
    """La regla «vacío hereda» también del lado del front: un 0 lo rompería."""
    js = TPL_JS.read_text(encoding="utf-8")
    ser = js[js.index("function serializarEscalas"):js.index("function plantillaEscala")]
    assert "? null :" in ser
    assert "activa: marcado('.esc-radio')" in ser
    assert "visible_pdf" in ser


def test_el_detalle_pinta_la_escala_guardada(client, entorno):
    pp = entorno["linea"]
    _escala(pp, cantidad=100, precio_unitario=Decimal("175.00"), activa=True)
    client.force_login(entorno["admin"])
    html = client.get(reverse("proyectos-detalle", args=[entorno["p"].pk])).content.decode()
    assert "escala-fila" in html
    assert 'value="100"' in html
    assert "escalas_json" in html


# ══════════════════════════════════════════════════════════════════════════════
# a/b — Los dos modales
# ══════════════════════════════════════════════════════════════════════════════


def test_al_aprobar_con_varias_opciones_sale_el_modal(client, entorno):
    from apps.cotizaciones import services
    pp = entorno["linea"]
    _escala(pp, cantidad=100, precio_unitario=Decimal("175.00"), orden=0)
    services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    client.force_login(entorno["admin"])
    resp = client.post(
        reverse("proyectos-cotizacion-estado", args=[entorno["p"].pk]),
        {"estado": "aprobada"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "¿Con cuál cantidad quedó?" in html
    assert 'id="modal-slot"' in html          # va por OOB sobre el panel


def test_elegir_deja_una_sola_opcion(client, entorno):
    pp = entorno["linea"]
    b = _escala(pp, cantidad=100, precio_unitario=Decimal("175.00"), orden=0)
    client.force_login(entorno["admin"])
    resp = client.post(
        reverse("proyectos-escalas-elegir", args=[entorno["p"].pk]),
        {f"opcion-{pp.pk}": str(b.pk)}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    pp.refresh_from_db()
    b.refresh_from_db()
    assert b.activa is True
    assert b.visible_pdf is True
    assert pp.visible_pdf is False            # la Opción A sale del documento
    assert pp.opciones_documento() == [b]


def test_elegir_la_opcion_a_apaga_las_escalas(client, entorno):
    pp = entorno["linea"]
    b = _escala(pp, cantidad=100, activa=True, orden=0)
    client.force_login(entorno["admin"])
    client.post(reverse("proyectos-escalas-elegir", args=[entorno["p"].pk]),
                {f"opcion-{pp.pk}": "a"}, HTTP_HX_REQUEST="true")
    pp.refresh_from_db()
    b.refresh_from_db()
    assert b.activa is False
    assert b.visible_pdf is False
    assert pp.visible_pdf is True
    assert pp.cantidad_efectiva == 70


def test_al_entrar_a_produccion_ofrece_aprobar_la_cotizacion(client, entorno):
    """Si el taller ya está trabajando, la cotización debería estar aprobada."""
    from apps.cotizaciones import services
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    cot.estado = "enviada"
    cot.save(update_fields=["estado"])
    client.force_login(entorno["admin"])
    resp = client.post(
        reverse("proyectos-cambiar-estado", args=[entorno["p"].pk]),
        {"estado": "en_proceso_diseno"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "pedirAprobarCotizacion" in resp.headers.get("HX-Trigger", "")


def test_no_ofrece_aprobar_si_ya_estaba_aprobada(client, entorno):
    from apps.cotizaciones import services
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    cot.estado = "aprobada"
    cot.save(update_fields=["estado"])
    client.force_login(entorno["admin"])
    resp = client.post(
        reverse("proyectos-cambiar-estado", args=[entorno["p"].pk]),
        {"estado": "en_proceso_diseno"}, HTTP_HX_REQUEST="true")
    assert "pedirAprobarCotizacion" not in resp.headers.get("HX-Trigger", "")


def test_no_ofrece_aprobar_al_cancelar(client, entorno):
    """Cancelar pregunta por su motivo, no por aprobar la cotización."""
    from apps.cotizaciones import services
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    cot.estado = "enviada"
    cot.save(update_fields=["estado"])
    client.force_login(entorno["admin"])
    resp = client.post(
        reverse("proyectos-cambiar-estado", args=[entorno["p"].pk]),
        {"estado": "cancelado"}, HTTP_HX_REQUEST="true")
    trigger = resp.headers.get("HX-Trigger", "")
    assert "pedirMotivoCancelacion" in trigger
    assert "pedirAprobarCotizacion" not in trigger


def test_el_modal_de_aprobar_apunta_al_estado_de_la_cotizacion(client, entorno):
    from apps.cotizaciones import services
    services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    client.force_login(entorno["admin"])
    html = client.get(reverse("proyectos-modal-aprobar-cotizacion",
                              args=[entorno["p"].pk])).content.decode()
    assert "¿Pasar la cotización a" in html
    assert reverse("proyectos-cotizacion-estado", args=[entorno["p"].pk]) in html
    assert '"estado": "aprobada"' in html


def test_duplicar_la_linea_clona_sus_escalas(client, entorno):
    pp = entorno["linea"]
    _escala(pp, cantidad=100, precio_unitario=Decimal("175.00"), activa=True)
    client.force_login(entorno["admin"])
    client.post(reverse("proyectos-duplicar-producto",
                        args=[entorno["p"].pk, pp.pk]), HTTP_HX_REQUEST="true")
    from apps.los_proyectos.models import ProyectoProducto
    copia = ProyectoProducto.objects.filter(proyecto=entorno["p"]).exclude(pk=pp.pk).get()
    assert copia.escalas.count() == 1
    assert copia.escalas.get().activa is True
    assert copia.cantidad_efectiva == 100


# ══════════════════════════════════════════════════════════════════════════════
# c/d — Márgenes, logotipo y pie del documento
# ══════════════════════════════════════════════════════════════════════════════


def test_las_peticiones_de_margenes_llevan_el_interruptor_del_pie():
    """Sin `useCustomHeaderFooterMargins`, Google IGNORA `marginFooter`."""
    from apps.cotizaciones.services import PAGINA_DOCUMENTO

    from lib.google_drive import _peticiones_pagina
    peticiones = _peticiones_pagina(PAGINA_DOCUMENTO)
    assert len(peticiones) == 1
    estilo = peticiones[0]["updateDocumentStyle"]
    assert estilo["documentStyle"]["marginTop"]["magnitude"] == 36
    assert estilo["documentStyle"]["marginBottom"]["magnitude"] == 43
    assert estilo["documentStyle"]["marginFooter"]["magnitude"] == 20
    assert estilo["documentStyle"]["useCustomHeaderFooterMargins"] is True
    for campo in ("marginTop", "marginBottom", "marginFooter",
                  "useCustomHeaderFooterMargins"):
        assert campo in estilo["fields"]


def test_sin_margenes_no_se_pide_nada():
    from lib.google_drive import _peticiones_pagina
    assert _peticiones_pagina({}) == []
    assert _peticiones_pagina({"pie_texto": "1/1"}) == []


def test_el_pie_se_escribe_al_final_del_segmento():
    """En un segmento recién creado el índice 0 es ambiguo; «al final» no."""
    from lib.google_drive import _id_del_pie, _peticiones_texto_pie
    assert _id_del_pie({"replies": [{}, {"createFooter": {"footerId": "kix.abc"}}]}) == "kix.abc"
    assert _id_del_pie({"replies": [{}]}) == ""
    assert _id_del_pie({}) == ""

    peticiones = _peticiones_texto_pie("kix.abc", "1/1")
    insertar = peticiones[0]["insertText"]
    assert insertar["endOfSegmentLocation"] == {"segmentId": "kix.abc"}
    assert insertar["text"] == "1/1"
    assert peticiones[1]["updateParagraphStyle"]["paragraphStyle"]["alignment"] == "CENTER"
    assert peticiones[2]["updateTextStyle"]["textStyle"]["fontSize"]["magnitude"] == 9


def test_ajustar_pagina_es_best_effort(monkeypatch):
    """Sin API de Documentos el PDF sale igual: devuelve False, nunca lanza."""
    from lib.google_drive import GoogleDriveWrapper
    wrapper = GoogleDriveWrapper()
    monkeypatch.setattr(wrapper, "_headers", lambda: (_ for _ in ()).throw(RuntimeError("sin token")))
    assert wrapper._ajustar_pagina("doc", {"margen_superior_pt": 36}) is False


def test_el_area_imprimible_crecio_diez_por_ciento():
    """Media pulgada arriba y 0.6 abajo: el encabezado sube y cabe ~10% más."""
    from apps.cotizaciones import services
    assert services._ALTO_UTIL_PT == 792 - 36 - 43
    assert pytest.approx(1.10, abs=0.01) == services._ALTO_UTIL_PT / 648
    # El pie vive DENTRO del margen inferior: no le quita nada al contenido.
    assert services._MARGEN_PIE_PT < services._MARGEN_INFERIOR_PT


def test_el_logotipo_crecio_cinco_por_ciento():
    tpl = TPL_PDF.read_text(encoding="utf-8")
    assert 'width="50" height="50"' in tpl
    assert "width:50pt; height:50pt" in tpl
    assert "48pt" not in tpl


def test_la_hoja_de_la_vista_previa_espeja_los_margenes():
    tpl = TPL_PDF.read_text(encoding="utf-8")
    assert "padding: 0.5in 1in 0.6in" in tpl
    # Y pinta el «1/1» para que se vea lo que llevará el PDF.
    assert "{{ pie_documento }}" in tpl


def test_generar_pdf_le_pasa_los_margenes_a_drive(monkeypatch, entorno):
    from apps.cotizaciones import services
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    capturado = {}

    class _Res:
        ok = False
        error = "sin Drive"

    def _falso(**kw):
        capturado.update(kw)
        return _Res()

    monkeypatch.setattr("lib.documentos.generar_pdf", _falso)
    services.generar_pdf(cot, entorno["admin"])
    assert capturado["pagina"] == services.PAGINA_DOCUMENTO
    assert capturado["pagina"]["pie_texto"] == "1/1"


def test_el_ojo_de_la_opcion_a_siempre_viaja_en_el_post(client, entorno):
    """Un checkbox que no se rendea no viaja en el POST y se guarda como False:
    si el ojo sólo se pintara con escalas, el autoguardado apagaría del documento
    a todas las líneas normales."""
    pp = entorno["linea"]
    client.force_login(entorno["admin"])
    url = reverse("proyectos-detalle", args=[entorno["p"].pk])
    html = client.get(url).content.decode()
    campo = "productos-0-visible_pdf"
    assert campo in html                      # está, aunque no haya escalas

    datos = dict(BASE_FORMSET)
    datos.update({
        "nombre": entorno["p"].nombre, "cliente": entorno["p"].cliente_id,
        "estado": entorno["p"].estado,
        "productos-TOTAL_FORMS": "1", "productos-INITIAL_FORMS": "1",
        "productos-0-id": str(pp.pk), "productos-0-servicio": str(entorno["srv"].pk),
        "productos-0-cantidad": "70", "productos-0-merma": "0",
        "productos-0-precio_unitario": "195.00",
        "productos-0-incluir_en_calculo": "on", "productos-0-visible_pdf": "on",
    })
    client.post(url, datos, HTTP_HX_REQUEST="true")
    pp.refresh_from_db()
    assert pp.visible_pdf is True


def test_el_override_de_impresion_cuenta_en_la_deuda_y_en_el_egreso(entorno):
    """Si la escala activa pisa el costo de impresión, ése es el que se le adeuda
    al proveedor y el que cobra el egreso — no el de la Opción A. Sin esto, el
    costo del proyecto decía una cosa y la deuda otra."""
    from apps.los_proyectos import gastos
    pp = entorno["linea"]
    _escala(pp, cantidad=100, activa=True,
            impresion_costo=Decimal("8.00"), impresion_por_pieza=True)
    pp.refresh_from_db()
    proc = pp.procesos.get(tipo="impresion")

    assert proc.costo_efectivo == Decimal("8.00")     # la escala pisó el 10
    assert proc.costo_total == Decimal("800.00")      # 8 × 100 piezas
    deuda = {d["proveedor"].pk: d["total"] for d in entorno["p"].deuda_por_proveedor()}
    # 100 × 80 del producto + 100 × 8 de impresión, al mismo proveedor.
    assert deuda[entorno["prov"].pk] == Decimal("8800.00")
    unidades = [u for u in gastos.iter_unidades(entorno["p"])
                if u["clase"] == "proceso"]
    assert unidades[0]["monto"] == Decimal("800.00")


def test_sin_override_la_impresion_no_cambia(entorno):
    """Regresión: una escala que hereda la impresión no altera la deuda."""
    pp = entorno["linea"]
    _escala(pp, cantidad=100, activa=True)            # impresión vacía = hereda
    pp.refresh_from_db()
    proc = pp.procesos.get(tipo="impresion")
    assert proc.costo_efectivo == Decimal("10.00")
    assert proc.costo_total == Decimal("1000.00")     # 10 × 100


def test_el_modal_de_escalas_solo_sale_a_quien_puede_aplicarlo(client, entorno,
                                                               usuario_factory):
    """Quien edita cotizaciones no necesariamente edita proyectos: mostrarle la
    pregunta sería ofrecerle algo que al confirmar contestaría 403."""
    from apps.cotizaciones import services
    pp = entorno["linea"]
    _escala(pp, cantidad=100, precio_unitario=Decimal("175.00"), orden=0)
    services.generar_desde_proyecto(entorno["p"], entorno["admin"])

    disenador = usuario_factory(rol="disenador")
    client.force_login(disenador)
    resp = client.post(
        reverse("proyectos-cotizacion-estado", args=[entorno["p"].pk]),
        {"estado": "aprobada"}, HTTP_HX_REQUEST="true")
    # Sin permiso de cotizaciones ni de proyecto: no hay modal (403 o panel).
    assert "¿Con cuál cantidad quedó?" not in resp.content.decode()


def test_editar_la_pestana_conserva_las_alternativas_del_documento(entorno):
    """`sincronizar_items` borra del documento lo que no reconoce. Sin enseñarle
    las escalas, editar una pestaña se llevaría los renglones que el cliente veía
    y el total cambiaría en silencio."""
    from apps.cotizaciones import services
    from apps.los_proyectos import services_version
    pp = entorno["linea"]
    _escala(pp, cantidad=100, precio_unitario=Decimal("175.00"), activa=True)
    _escala(pp, cantidad=200, precio_unitario=Decimal("160.00"), orden=1)
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    antes = cot.calcular_totales()["subtotal_items"]
    assert cot.items.filter(informativo=True).count() == 2

    services_version.sincronizar_items(cot)

    cot.refresh_from_db()
    assert cot.items.filter(informativo=True).count() == 2
    # La línea que suma sigue siendo la de la opción activa.
    principal = cot.items.get(informativo=False, agrupado=False)
    assert principal.cantidad == Decimal("100.00")
    assert cot.calcular_totales()["subtotal_items"] == antes


def test_la_pestana_no_apaga_el_cobro_de_una_venta(entorno):
    """La cola de líneas reutilizables mezcla ventas y alternativas: si no se
    apaga la bandera al reusar, una venta dejaría de sumar."""
    from apps.cotizaciones import services
    from apps.los_proyectos import services_version
    from apps.los_proyectos.models import ProyectoProductoVenta
    pp = entorno["linea"]
    ProyectoProductoVenta.objects.create(
        producto=pp, descripcion="Ponchado", cantidad=1,
        precio_unitario=Decimal("350.00"), orden=0)
    _escala(pp, cantidad=100, precio_unitario=Decimal("175.00"), activa=True)
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    services_version.sincronizar_items(cot)

    venta = cot.items.get(concepto="Ponchado")
    assert venta.informativo is False
    assert venta.agrupado is True
    # 100 × 175 del producto + 350 del Ponchado; la alternativa (70 × 195) no suma.
    assert cot.calcular_totales()["subtotal_items"] == Decimal("17850.00")


def test_la_sub_fila_conserva_sus_etiquetas_en_el_celular():
    """Las etiquetas van DENTRO de la celda de su campo. En un renglón aparte se
    veían igual en escritorio, pero en el celular la rejilla baja a 2 columnas y
    las etiquetas no pueden alinearse con los inputs: la sub-fila quedaba como
    cinco números sin nombre."""
    tpl = TPL_ESCALA.read_text(encoding="utf-8")
    assert "hidden gap-2 md:grid" not in tpl        # nada de etiquetas sólo-desktop
    # Cada campo trae su etiqueta pegada arriba.
    for etiqueta, clase in (("Cantidad", "esc-cant"), ("Merma", "esc-merma"),
                            ("Precio unit.", "esc-precio"),
                            ("Costo unit.", "esc-costo"), ("Impresión", "esc-imp")):
        i = tpl.index(f">{etiqueta}")
        assert clase in tpl[i:i + 700], (etiqueta, clase)
    js = TPL_JS.read_text(encoding="utf-8")
    plantilla = js[js.index("function plantillaEscala"):js.index("function agregarEscala")]
    assert "hidden gap-2" not in plantilla
    for etiqueta in ("Cantidad", "Merma", "Precio unit.", "Costo unit.", "Impresión"):
        assert etiqueta in plantilla, etiqueta
