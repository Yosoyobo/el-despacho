"""Ajustes LC 2026-07-25 (VERSION 2026.07.29).

1. Panel de Cotizaciones del proyecto: «Ver →» abre la PÁGINA de la cotización.
2. Dashboard: los 3 controles de El Chalán en la misma línea.
3. Resumen de actividad: encabezado con fecha/hora, fechas con día de la semana
   y mes completo, nada vencido, TIZAYUCA por producto con merma incluida.
4. Página de Cotizaciones: tabla por default, pastillas de estado con color,
   versión pegada al nombre del proyecto, orden por proyecto, botón ✕.
5. El Chalán edita/sobreescribe ingresos, egresos y facturas.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _seccion(secciones, titulo):
    return next((s for s in secciones if s["titulo"] == titulo), None)


def _cotizacion(proyecto, autor, *, codigo="COT-2026-9001", version=1, estado="generada"):
    from apps.cotizaciones.models import Cotizacion
    return Cotizacion.objects.create(
        codigo=codigo, cliente=proyecto.cliente, proyecto=proyecto, titulo="Propuesta",
        estado=estado, version=version, creado_por=autor, fecha_emision=dt.date.today(),
    )


# ── 1) «Ver →» del panel del proyecto ────────────────────────────────────


def test_panel_del_proyecto_enlaza_a_la_pagina_de_la_cotizacion(
        client, proyecto_factory, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Gorras MAU")
    cot = _cotizacion(p, admin)
    client.force_login(admin)

    html = client.get(f"/proyectos/{p.pk}/").content.decode()
    assert f'href="/cotizaciones/{cot.pk}/"' in html          # la página
    assert f'href="/cotizaciones/{cot.pk}/ver/"' not in html  # ya no el PDF


# ── 2) Los controles de El Chalán en la misma línea ──────────────────────


def test_dashboard_tiene_los_controles_del_chalan_en_una_linea(
        client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/").content.decode()

    assert "flex-nowrap" in html
    # Tercera ronda: el botón se renombró a «Resumir pendientes».
    assert "Resumir pendientes" in html
    assert ">Enviar<" in html
    # Oscar 2026-07-25 (segunda ronda): el atajo «Abrir chat» se quitó — el
    # acceso al chat vive en el sidebar («El Chalán»).
    assert "Abrir chat" not in html
    assert "Abrir el chat de El Chalán" not in html


# ── 3) Reporte de actividad ──────────────────────────────────────────────


def test_encabezado_trae_dia_fecha_y_hora():
    from apps.taller_home.pendientes import encabezado_fecha
    from django.utils import timezone

    ahora = timezone.localtime()
    texto = encabezado_fecha()
    dias = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    assert dias[ahora.weekday()] in texto
    assert f"de {ahora.year}" in texto
    assert "·" in texto  # separador antes de la hora


def test_fechas_con_dia_de_la_semana_y_mes_completo(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea
    from apps.taller_home.pendientes import secciones_pendientes

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    manana = dt.date.today() + dt.timedelta(days=1)
    Tarea.objects.create(proyecto=p, titulo="Entregar", prioridad="alta",
                         fecha_compromiso=manana)

    linea = _seccion(secciones_pendientes(admin), "URGENTES")["lineas"][0]
    meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre")
    dias = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    assert meses[manana.month - 1] in linea
    assert dias[manana.weekday()] in linea
    assert f"{manana.day} de " in linea


def test_nada_vencido_salvo_las_cuentas_por_cobrar(proyecto_factory, usuario_factory):
    """Los proyectos con fecha pasada no entran. Las cuentas por cobrar SÍ,
    aunque estén vencidas: se quedan hasta que se cobren o se liguen."""
    from apps.facturacion.models import Factura, FacturaItem
    from apps.taller_home.pendientes import secciones_pendientes

    admin = usuario_factory(rol="super_admin")
    ayer = dt.date.today() - dt.timedelta(days=1)
    proyecto_factory(nombre="Proyecto atrasado", estado="por_cotizar",
                     fecha_compromiso=ayer)
    vigente = proyecto_factory(nombre="Proyecto al día", estado="por_cotizar",
                               fecha_compromiso=dt.date.today())
    fac = Factura.objects.create(
        cliente=vigente.cliente, proyecto=vigente, estado="emitida", concepto="Servicios",
        fecha_emision=ayer, fecha_vencimiento=ayer,
    )
    FacturaItem.objects.create(factura=fac, descripcion="Trabajo", cantidad=1,
                               precio_unitario=1000)

    secs = secciones_pendientes(admin)
    cotizaciones = "\n".join(_seccion(secs, "COTIZACIONES")["lineas"])
    assert "Proyecto al día" in cotizaciones
    assert "Proyecto atrasado" not in cotizaciones
    # Excepción: la factura vencida con saldo sigue en la lista de cobro.
    assert fac.codigo in "\n".join(_seccion(secs, "CUENTAS X COBRAR")["lineas"])


def test_tizayuca_un_renglon_por_producto_con_merma(proyecto_factory, usuario_factory):
    from apps.el_catalogo.calculadora import PROVEEDOR_CALCULADORA
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    from apps.taller_home.pendientes import secciones_pendientes

    admin = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social=PROVEEDOR_CALCULADORA, activo=True)
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat")
    funda = Servicio.objects.create(nombre="Funda", categoria=cat, activo=True,
                                    precio_base="100.00")
    porta = Servicio.objects.create(nombre="Portagafete", categoria=cat, activo=True,
                                    precio_base="50.00")
    otro = Servicio.objects.create(nombre="Playera", categoria=cat, activo=True,
                                   precio_base="80.00")
    p = proyecto_factory(nombre="Fundas Tizayuca")
    ProyectoProducto.objects.create(proyecto=p, servicio=funda, cantidad=100,
                                    merma=5, proveedor=prov)
    ProyectoProducto.objects.create(proyecto=p, servicio=porta, cantidad=30,
                                    merma=0, proveedor=prov)
    ProyectoProducto.objects.create(proyecto=p, servicio=otro, cantidad=10)

    lineas = _seccion(secciones_pendientes(admin), "TIZAYUCA")["lineas"]
    texto = "\n".join(lineas)
    assert len(lineas) == 2                       # un renglón por producto
    assert "Funda x 105 pz" in texto              # cantidad + merma
    assert "Portagafete x 30 pz" in texto
    assert "Playera" not in texto                 # no es de ese proveedor
    assert p.cliente.razon_social in lineas[0]


def test_modal_resumen_arranca_con_el_encabezado(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)

    html = client.get("/resumen/actividad/", HTTP_HX_REQUEST="true").content.decode()
    cuerpo = html.split('id="reporte-pendientes"', 1)[1]
    assert cuerpo.index("<b>") < cuerpo.index("<b>URGENTES</b>")


# ── 4) Página de Cotizaciones ────────────────────────────────────────────


def test_vista_default_es_tabla(client, proyecto_factory, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Correas")
    _cotizacion(p, admin, version=2)
    client.force_login(admin)

    html = client.get("/cotizaciones/").content.decode()
    assert "cabeceras" in html or "<table" in html
    assert "<table" in html                     # tabla, no tarjetas
    assert ">Versión<" not in html              # la columna se fue
    assert ">v2<" in html                       # la versión va con el nombre


def test_pastillas_de_estado_traen_su_color(client, proyecto_factory, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)

    html = client.get("/cotizaciones/").content.decode()
    assert "pill-estado" in html
    assert "--ec:" in html
    assert "Vigentes" in html and "Anuladas" in html


def test_buscador_de_cliente_va_antes_de_las_pastillas(client, proyecto_factory,
                                                       usuario_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Correas")
    _cotizacion(p, admin)
    client.force_login(admin)

    html = client.get("/cotizaciones/").content.decode()
    barra = html.split('aria-label="Filtrar por cliente"', 1)[1]
    assert barra.index("data-select-buscable") < barra.index(">Todos<")
    assert "flex-nowrap" in html                # los recientes, en una línea


def test_orden_por_proyecto_es_alfabetico_con_la_version_mas_nueva_arriba(
        client, proyecto_factory, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    zeta = proyecto_factory(nombre="Zapatos")
    alfa = proyecto_factory(nombre="Alfombras")
    _cotizacion(zeta, admin, codigo="COT-2026-9010", version=1)
    _cotizacion(alfa, admin, codigo="COT-2026-9011", version=1)
    _cotizacion(alfa, admin, codigo="COT-2026-9012", version=2)
    client.force_login(admin)

    r = client.get("/cotizaciones/?orden=proyecto")
    codigos = [c.codigo for c in r.context["cotizaciones"]]
    assert codigos == ["COT-2026-9012", "COT-2026-9011", "COT-2026-9010"]


def test_boton_equis_anula_y_en_anuladas_elimina(client, proyecto_factory,
                                                 usuario_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Correas")
    viva = _cotizacion(p, admin, codigo="COT-2026-9020")
    anulada = _cotizacion(p, admin, codigo="COT-2026-9021", estado="anulada")
    client.force_login(admin)

    html = client.get("/cotizaciones/").content.decode()
    assert f"/cotizaciones/{viva.pk}/anular/" in html

    html_anuladas = client.get("/cotizaciones/?estado=anulada").content.decode()
    assert f"/cotizaciones/{anulada.pk}/eliminar/" in html_anuladas


# ── 5) El Chalán edita ingresos, egresos y facturas ──────────────────────


def _accion(tipo: str, payload: dict):
    """DictadoAccion en memoria — el ejecutor solo lee `payload` y escribe
    `entidad_*`, así que no hace falta persistir el Dictado."""
    from apps.el_dictado.models import DictadoAccion
    return DictadoAccion(tipo=tipo, payload=payload, orden=0)


def _ingreso(admin, proyecto, **kw):
    from apps.tesoreria.models import Ingreso
    datos = {"monto": Decimal("5000.00"), "descripcion": "Anticipo",
             "fecha": dt.date.today(), "metodo": "transferencia",
             "cliente": proyecto.cliente, "proyecto": proyecto, "creado_por": admin}
    datos.update(kw)
    return Ingreso.objects.create(**datos)


def _egreso(admin, **kw):
    from apps.tesoreria.models import CentroDeCosto, Egreso
    centro = CentroDeCosto.objects.filter(activo=True).first() \
        or CentroDeCosto.objects.create(nombre="Otros", slug="otros", activo=True)
    datos = {"monto": Decimal("450.00"), "descripcion": "Papelería",
             "fecha": dt.date.today(), "centro_de_costo": centro,
             "estado_pago": "pagado", "metodo": "transferencia", "creado_por": admin}
    datos.update(kw)
    return Egreso.objects.create(**datos)


def test_actualizar_ingreso_corrige_descripcion_y_metodo(proyecto_factory,
                                                         usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    ing = _ingreso(admin, p)
    accion = _accion("actualizar_ingreso", {
        "codigo": ing.codigo,
        "campos": {"descripcion": "Anticipo corregido", "metodo": "efectivo"},
    })
    EJECUTORES["actualizar_ingreso"](accion, admin, {})

    ing.refresh_from_db()
    assert ing.descripcion == "Anticipo corregido"
    assert ing.metodo == "efectivo"
    assert ing.monto == Decimal("5000.00")   # intacto
    assert accion.entidad_tipo == "ingreso"


def test_el_monto_de_un_movimiento_no_se_puede_editar(proyecto_factory,
                                                      usuario_factory):
    """Decisión Oscar: si el asiento no se reajusta, no se permite el cambio —
    se anula y se captura de nuevo."""
    from apps.el_dictado.ejecutores import EJECUTORES

    admin = usuario_factory(rol="super_admin")
    ing = _ingreso(admin, proyecto_factory())
    eg = _egreso(admin)

    with pytest.raises(ValueError, match="no se puede cambiar"):
        EJECUTORES["actualizar_ingreso"](
            _accion("actualizar_ingreso", {"codigo": ing.codigo,
                                           "campos": {"monto": "6500"}}), admin, {})
    with pytest.raises(ValueError, match="no se puede cambiar"):
        EJECUTORES["actualizar_egreso"](
            _accion("actualizar_egreso", {"codigo": eg.codigo,
                                          "campos": {"monto": "999"}}), admin, {})

    ing.refresh_from_db()
    eg.refresh_from_db()
    assert ing.monto == Decimal("5000.00")
    assert eg.monto == Decimal("450.00")


def test_el_catalogo_advierte_que_el_monto_no_es_editable():
    from lib.dictado_catalogo import COMANDOS_DICTADO

    por_tipo = {c["tipo"]: c for c in COMANDOS_DICTADO}
    for tipo in ("actualizar_ingreso", "actualizar_egreso"):
        assert "monto" not in por_tipo[tipo]["payload"].split(".")[0]
        assert "MONTO no se puede cambiar" in por_tipo[tipo]["payload"]


def test_actualizar_ingreso_rechaza_anulado(proyecto_factory, usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    admin = usuario_factory(rol="super_admin")
    ing = _ingreso(admin, proyecto_factory(), anulado=True)
    accion = _accion("actualizar_ingreso", {"codigo": ing.codigo,
                                            "campos": {"descripcion": "x"}})
    with pytest.raises(ValueError, match="anulado"):
        EJECUTORES["actualizar_ingreso"](accion, admin, {})


def test_actualizar_egreso_cambia_estado_y_proveedor(usuario_factory):
    from apps.el_catalogo.models import Proveedor
    from apps.el_dictado.ejecutores import EJECUTORES

    admin = usuario_factory(rol="super_admin")
    Proveedor.objects.create(razon_social="Telas del Norte", activo=True)
    eg = _egreso(admin)
    accion = _accion("actualizar_egreso", {
        "codigo": eg.codigo,
        "campos": {"estado_pago": "pendiente", "proveedor": "Telas del Norte"},
    })
    EJECUTORES["actualizar_egreso"](accion, admin, {})

    eg.refresh_from_db()
    assert eg.estado_pago == "pendiente"
    assert eg.proveedor.razon_social == "Telas del Norte"
    assert eg.proveedor_nombre == "Telas del Norte"


def test_actualizar_egreso_sin_campos_falla(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    admin = usuario_factory(rol="super_admin")
    eg = _egreso(admin)
    accion = _accion("actualizar_egreso", {"codigo": eg.codigo, "campos": {}})
    with pytest.raises(ValueError, match="ningún campo"):
        EJECUTORES["actualizar_egreso"](accion, admin, {})


def test_actualizar_factura_borrador_fija_monto_en_una_linea(proyecto_factory,
                                                             usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.facturacion.models import Factura

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    fac = Factura.objects.create(
        cliente=p.cliente, proyecto=p, estado="borrador", concepto="Producción",
        fecha_emision=dt.date.today(), fecha_vencimiento=dt.date.today(),
        creado_por=admin,
    )
    accion = _accion("actualizar_factura", {
        "codigo": fac.codigo,
        # Oscar 2026-07-25 (tercera ronda): una sola cifra dictada es el importe
        # FINAL de pago, así que `monto` fija el TOTAL y el sistema despeja la
        # base. Para dictar la base va `monto_base` (ver el test de abajo).
        "campos": {"monto": "33770", "concepto": "Producción de elementos"},
    })
    EJECUTORES["actualizar_factura"](accion, admin, {})

    fac.refresh_from_db()
    assert fac.concepto == "Producción de elementos"
    assert fac.items.count() == 1
    assert fac.calcular_totales()["total"] == Decimal("33770.00")


def test_actualizar_factura_monto_base_no_lleva_impuestos_dentro(proyecto_factory,
                                                                 usuario_factory):
    """`monto_base` es el subtotal: los impuestos se suman encima."""
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.facturacion.models import Factura

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    fac = Factura.objects.create(
        cliente=p.cliente, proyecto=p, estado="borrador", concepto="Producción",
        fecha_emision=dt.date.today(), fecha_vencimiento=dt.date.today(),
        creado_por=admin,
    )
    accion = _accion("actualizar_factura", {
        "codigo": fac.codigo, "campos": {"monto_base": "33770"},
    })
    EJECUTORES["actualizar_factura"](accion, admin, {})

    fac.refresh_from_db()
    assert fac.calcular_totales()["subtotal_items"] == Decimal("33770.00")


def test_actualizar_factura_emitida_no_se_toca(proyecto_factory, usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.facturacion.models import Factura

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    fac = Factura.objects.create(
        cliente=p.cliente, proyecto=p, estado="emitida", concepto="Producción",
        fecha_emision=dt.date.today(), fecha_vencimiento=dt.date.today(),
        creado_por=admin,
    )
    accion = _accion("actualizar_factura", {"codigo": fac.codigo,
                                            "campos": {"monto": "100"}})
    with pytest.raises(ValueError, match="editable"):
        EJECUTORES["actualizar_factura"](accion, admin, {})


def test_disenador_no_puede_editar_dinero(proyecto_factory, usuario_factory):
    """Defensa en profundidad: el catálogo ya no se lo ofrece, pero el ejecutor
    re-chequea el permiso antes de tocar la DB."""
    from apps.el_dictado.ejecutores import EJECUTORES

    admin = usuario_factory(rol="super_admin")
    disenador = usuario_factory(rol="disenador", email="dis@ejemplo.com")
    ing = _ingreso(admin, proyecto_factory())
    accion = _accion("actualizar_ingreso", {"codigo": ing.codigo,
                                            "campos": {"descripcion": "x"}})
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["actualizar_ingreso"](accion, disenador, {})


def test_catalogo_ofrece_los_tres_comandos_de_edicion(usuario_factory):
    from lib.dictado_catalogo import comandos_para

    admin = usuario_factory(rol="super_admin")
    tipos = {c["tipo"] for c in comandos_para(admin)}
    assert {"actualizar_ingreso", "actualizar_egreso", "actualizar_factura"} <= tipos

    disenador = usuario_factory(rol="disenador", email="dis2@ejemplo.com")
    tipos_dis = {c["tipo"] for c in comandos_para(disenador)}
    assert not ({"actualizar_ingreso", "actualizar_egreso", "actualizar_factura"}
                & tipos_dis)


def test_las_tres_acciones_son_capacidades_de_propuesta_v2():
    """Al estar en el catálogo, el chat las expone como tools de propuesta
    (nombre == tipo) — nunca se auto-aplican."""
    from capacidades import CAPACIDADES, MODO_PROPUESTA

    for tipo in ("actualizar_ingreso", "actualizar_egreso", "actualizar_factura"):
        cap = CAPACIDADES.get(tipo)
        assert cap is not None and cap.modo == MODO_PROPUESTA


# ── 6) Formato del documento (notas de Oscar sobre el PDF) ───────────────


def _cot_con_producto(proyecto, autor):
    """Cotización con una línea real, para renderizar el documento."""
    from apps.cotizaciones.models import CotizacionItem
    cot = _cotizacion(proyecto, autor, codigo="COT-2026-9100")
    CotizacionItem.objects.create(
        cotizacion=cot, concepto="Gorras", descripcion="105 pz (3 colores)",
        cantidad=105, precio_unitario=Decimal("120.00"),
    )
    return cot


def test_titulo_del_documento_es_el_formato_de_lc(proyecto_factory, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Ted Lasso")
    cot = _cotizacion(p, admin, codigo="COT-2026-9101")

    assert cot.titulo_documento == "Producción de elementos para proyecto 'Ted Lasso'"


def test_pdf_sin_lineas_encabezado_gris_logo_chico_y_notas_al_pie(
        proyecto_factory, usuario_factory):
    from apps.cotizaciones.services import construir_html_pdf

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Ted Lasso")
    cot = _cot_con_producto(p, admin)
    cot.incluir_desglose = True
    cot.save()

    html = construir_html_pdf(cot)
    # (5) título fijo
    assert "Producción de elementos para proyecto &#x27;Ted Lasso&#x27;" in html \
        or "Producción de elementos para proyecto 'Ted Lasso'" in html
    # (1) las tablas de conceptos llevan recuadro GRIS CLARO (Oscar 2026-07-26:
    # «el outline de la línea debe de ser gris claro, no negro»); el encabezado,
    # los totales y las notas siguen sin líneas.
    assert "border:1px solid #000000" not in html
    assert html.count("border:1px solid #cccccc") >= 8
    # (3) encabezados con fondo gris clarito
    assert html.count("background-color:#f2f2f2") >= 4
    # (2) logo más chico
    assert "width:48pt; height:48pt" in html
    # (4) notas empujadas al pie. Oscar 2026-07-25 (segunda ronda): el hueco
    # dejó de ser fijo (108pt) y ahora se calcula según lo que quepa en la hoja.
    assert "margin-top:108pt" not in html
    # `rindex`: desde 2026-07-26 cada bloque de producto y el desglose también
    # llevan `page-break-inside:avoid` (no se parten entre páginas); el ÚLTIMO
    # es el de las notas, que va al final del documento.
    assert html.rindex("page-break-inside:avoid") > html.index("Gorras")


# ── 7) El alias del producto manda en los recuadros del proyecto ─────────


def test_nombre_ajustado_en_desglose_y_proveedores(client, proyecto_factory,
                                                   usuario_factory):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat")
    srv = Servicio.objects.create(nombre="TShirt Oversize Color", categoria=cat,
                                  activo=True, precio_base="200.00", costo="80.00")
    prov = Proveedor.objects.create(razon_social="Crea Blanks", activo=True)
    p = proyecto_factory(nombre="Ted Lasso")
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=10,
                                    proveedor=prov, nombre_proyecto="TShirt Modelo Janet")
    client.force_login(admin)

    from apps.los_proyectos.views import _proveedores_panel

    html = client.get(f"/proyectos/{p.pk}/").content.decode()
    assert "TShirt Modelo Janet" in html
    # Recuadro «Desglose» (panel económico del sidebar): el alias, no el catálogo.
    # (el nombre del catálogo sigue en el JSON de datos que usa el JS del form).
    bloque = html.split("Aplicar IVA", 1)[0].rsplit("Desglose", 1)[-1] if "Desglose" in html else html
    assert "TShirt Modelo Janet" in bloque
    # Recuadro «Proveedores»: el concepto usa el alias.
    conceptos = [c["nombre"] for fila in _proveedores_panel(p) for c in fila["conceptos"]]
    assert "TShirt Modelo Janet" in conceptos
    assert "TShirt Oversize Color" not in conceptos


# ── 8) Formato del documento, segunda tanda ──────────────────────────────


def test_titulo_del_concepto_sale_del_nombre_no_de_las_especificaciones(
        proyecto_factory, usuario_factory):
    """Línea vieja (sin `concepto`) pero con producto: el título numerado toma
    el nombre del catálogo, no el primer renglón de las especificaciones."""
    from apps.cotizaciones.models import CotizacionItem
    from apps.el_catalogo.models import CategoriaServicio, Servicio

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat")
    srv = Servicio.objects.create(nombre="Gorras de gabardina", categoria=cat,
                                  activo=True, precio_base="120.00")
    p = proyecto_factory(nombre="Ted Lasso")
    cot = _cotizacion(p, admin, codigo="COT-2026-9102")
    it = CotizacionItem.objects.create(
        cotizacion=cot, servicio=srv, concepto="",
        descripcion="105 pz (3 colores, 35 pz c/u)\nColor: Beige",
        cantidad=105, precio_unitario=Decimal("120.00"),
    )

    assert it.concepto_visible == "Gorras de gabardina"
    # …y la primera especificación NO se pierde (antes se la comía el legacy).
    assert it.detalle_lineas[0] == "105 pz (3 colores, 35 pz c/u)"


def test_desglose_de_impuestos_sin_porcentajes(proyecto_factory, usuario_factory):
    from apps.cotizaciones.services import construir_html_pdf

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Ted Lasso")
    p.regimen_fiscal = "honorarios"
    p.save()
    cot = _cot_con_producto(p, admin)
    cot.regimen_fiscal = "honorarios"
    cot.incluir_desglose = True
    cot.save()

    html = construir_html_pdf(cot)
    assert "Retención de IVA" in html
    assert "10.6667%" not in html
    assert "Retención de IVA (" not in html


def test_tabla_de_montos_centrada_acotada_y_de_un_renglon(proyecto_factory,
                                                          usuario_factory):
    from apps.cotizaciones.services import construir_html_pdf

    admin = usuario_factory(rol="super_admin")
    cot = _cot_con_producto(proyecto_factory(nombre="Ted Lasso"), admin)

    html = construir_html_pdf(cot)
    # Oscar 2026-07-26 (cuarta ronda): ni `margin:0 auto` ni `align="center"`
    # centraron la tabla en Docs. Lo que sí funciona es una columna vacía a cada
    # lado dentro de la misma tabla. Y como el convertidor ignora
    # `white-space:nowrap`, el encabezado se mantiene corto.
    assert 'style="border:none; width:11%;"' in html
    assert "P. Unitario" in html


def test_sin_especificaciones_ni_foto_no_queda_tabla_vacia(proyecto_factory,
                                                           usuario_factory):
    """El hueco entre el nombre numerado y la tabla de montos desaparece."""
    from apps.cotizaciones.models import CotizacionItem
    from apps.cotizaciones.services import construir_html_pdf

    admin = usuario_factory(rol="super_admin")
    cot = _cotizacion(proyecto_factory(nombre="Ted Lasso"), admin, codigo="COT-2026-9103")
    CotizacionItem.objects.create(cotizacion=cot, concepto="Gorras", descripcion="",
                                  cantidad=1, precio_unitario=Decimal("100.00"))

    html = construir_html_pdf(cot)
    # Del nombre subrayado se pasa directo a la tabla de montos: en medio se
    # cierra la celda del nombre y arranca la tabla, sin una fila de
    # especificaciones vacía. (La tabla de montos ya no lleva `<thead>`, así que
    # el corte se hace en su etiqueta `<table`.)
    entre = html.split("<u>Gorras</u>", 1)[1].split("<table", 1)[0]
    assert "<td" not in entre
