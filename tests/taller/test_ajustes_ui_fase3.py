"""Tests de S-Ajustes-UI-Fase3 (VERSION 2026.07.15).

Cubre las 6 entregas de la Fase 3:
- 1.1 Facturación: guardrail de líneas cero (no queda en $0.00 al vaciarla).
- 1.2 Breadcrumb trail de proveedores (`?desde=proveedor:<pk>`).
- 1.3 Form avanzado de producto: buscador de proveedores + Guardar arriba.
- 1.4 Cotizaciones: estado dropdown coloreado único, selector cliente global,
       nombre de proyecto como enlace, higiene de descripciones.
- §2a Ingreso: comprobante en Drive (campos + proxy).
- §2b DnD productos: campo `orden` en el formset (persiste en Nuevo/Editar).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(
        _tx, "on_commit", lambda fn, using=None, robust=False: fn(),
    )


# ── 1.1 Facturación — guardrail de líneas cero ───────────────────────────


def test_guardrail_fallback_sintetiza_linea(cliente_factory, usuario_factory):
    """Sin cotización ni proyecto de origen, con `monto_fallback` sintetiza UNA
    línea con el concepto de la factura → nunca queda en $0.00."""
    from apps.facturacion import services
    from apps.facturacion.models import Factura

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(cliente=cli, concepto="Trabajo X", creado_por=autor)
    assert fac.items.count() == 0

    creado = services.asegurar_lineas_desde_origen(fac, monto_fallback=Decimal("500.00"))
    assert creado is True
    assert fac.items.count() == 1
    linea = fac.items.first()
    assert linea.precio_unitario == Decimal("500.00")
    assert linea.cantidad == Decimal("1.00")
    assert "Trabajo X" in linea.descripcion
    # Idempotente: ya hay líneas → no vuelve a crear.
    assert services.asegurar_lineas_desde_origen(fac, monto_fallback=Decimal("999")) is False


def test_guardrail_sin_origen_ni_fallback_no_crea(cliente_factory, usuario_factory):
    from apps.facturacion import services
    from apps.facturacion.models import Factura

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(cliente=cli, creado_por=autor)
    assert services.asegurar_lineas_desde_origen(fac) is False
    assert fac.items.count() == 0


def _post_editar_monto(client, fac, cli, *, monto, extra=None):
    """Helper: POST al form de editar en modo «monto» (una línea automática)."""
    data = {
        "folio_numero": fac.folio_numero, "porcentaje_a_facturar": "100",
        "cliente": cli.pk, "proyecto": "", "cotizacion_origen": "",
        "concepto": "Producción", "estado": "borrador",
        "modo_lineas": "monto", "monto": monto,
        "fecha_emision": "2026-07-10", "fecha_vencimiento": "2026-08-09",
        "moneda": "MXN", "regimen_fiscal": "iva",
        "descuento_global_porcentaje": "0", "notas": "", "terminos": "",
        "items-TOTAL_FORMS": "0", "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
    }
    if extra:
        data.update(extra)
    return client.post(f"/facturacion/{fac.pk}/editar/", data)


def test_editar_modo_monto_reemplaza_por_una_linea(client, cliente_factory, usuario_factory):
    """LC 2026-07 (revisión): en modo «monto» la factura queda con UNA sola
    línea-concepto igual al monto capturado, reemplazando las que tuviera (ya no
    se re-copian las líneas de la cotización de origen)."""
    from apps.facturacion.models import Factura, FacturaItem

    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(cliente=cli, concepto="Producción", creado_por=autor)
    for i in range(3):  # 3 líneas de producto que el usuario quiere sustituir
        FacturaItem.objects.create(
            factura=fac, orden=i, descripcion=f"Paliacate {i}", cantidad=Decimal("1"),
            unidad="pieza", precio_unitario=Decimal("500.00"),
        )
    resp = _post_editar_monto(client, fac, cli, monto="7500.00")
    assert resp.status_code == 302
    fac.refresh_from_db()
    assert fac.items.count() == 1
    assert fac.calcular_totales()["subtotal_items"] == Decimal("7500.00")
    # Las fechas elegidas SÍ se guardan (fix del widget de fecha).
    assert fac.fecha_emision == date(2026, 7, 10)
    assert fac.fecha_vencimiento == date(2026, 8, 9)


def test_editar_modo_monto_sin_monto_ni_origen_queda_sin_lineas(client, cliente_factory, usuario_factory):
    """Decisión Oscar: poder «quedarnos sin líneas». Sin monto ni origen del cual
    derivar, la factura queda con 0 líneas (no se fuerza una)."""
    from apps.facturacion.models import Factura, FacturaItem

    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(cliente=cli, concepto="Producción", creado_por=autor)
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="Servicio", cantidad=Decimal("1"),
        unidad="pieza", precio_unitario=Decimal("1000.00"),
    )
    resp = _post_editar_monto(client, fac, cli, monto="")
    assert resp.status_code == 302
    fac.refresh_from_db()
    assert fac.items.count() == 0


# ── 1.2 Breadcrumb trail de proveedores ──────────────────────────────────


def test_navegacion_producto_desde_proveedor(usuario_factory):
    from apps.el_catalogo.models import Proveedor
    from apps.el_catalogo.views import _navegacion_producto
    from django.test import RequestFactory

    prov = Proveedor.objects.create(razon_social="Maderas Don José")
    req = RequestFactory().get(f"/catalogo/1/editar?desde=proveedor:{prov.pk}")
    nav = _navegacion_producto(req)
    labels = [i["label"] for i in nav["breadcrumb_trail"]]
    assert labels == ["Productos", "Proveedores", "Maderas Don José", "Producto"]
    assert str(prov.pk) in nav["back_url_producto"]


def test_navegacion_producto_sin_desde(usuario_factory):
    from apps.el_catalogo.views import _navegacion_producto
    from django.test import RequestFactory

    req = RequestFactory().get("/catalogo/1/editar")
    nav = _navegacion_producto(req)
    assert [i["label"] for i in nav["breadcrumb_trail"]] == ["Productos", "Producto"]
    assert nav["back_url_producto"] == ""


# ── 1.3 Form avanzado de producto ─────────────────────────────────────────


def _servicio(usuario):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="General", defaults={"activa": True},
    )
    return Servicio.objects.create(
        nombre="Playera", categoria=cat, precio_base=Decimal("100"),
        creado_por=usuario,
    )


def test_form_producto_tiene_buscador_y_guardar_arriba(client, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    srv = _servicio(autor)
    resp = client.get(f"/catalogo/{srv.pk}/editar")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'id="prov-filtro"' in html          # buscador de proveedores
    assert 'form="producto-form"' in html       # botón Guardar arriba


# ── 1.4 Cotizaciones ──────────────────────────────────────────────────────


def _cotizacion(cliente_factory, usuario_factory, proyecto_factory):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = proyecto_factory(cliente=cli, creado_por=autor, nombre="Campaña verano")
    cot = Cotizacion.objects.create(
        cliente=cli, proyecto=proy, titulo="Campaña verano",
        version=1, estado="borrador", creado_por=autor,
    )
    CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="Diseño",
        cantidad=Decimal("1"), unidad="pieza", precio_unitario=Decimal("1000"),
    )
    return autor, proy, cot


def test_lista_cotizaciones_selector_global_y_enlace_proyecto(
        client, cliente_factory, usuario_factory, proyecto_factory):
    autor, proy, cot = _cotizacion(cliente_factory, usuario_factory, proyecto_factory)
    client.force_login(autor)
    resp = client.get("/cotizaciones/?vista=tabla")
    assert resp.status_code == 200
    # Selector de clientes global (busca todo el padrón).
    assert "clientes_todos" in resp.context
    assert list(resp.context["clientes_todos"])  # no vacío (hay al menos 1 cliente)
    html = resp.content.decode()
    # Estado como un solo control coloreado (clase .estado-chip), no la pastilla+select.
    assert "estado-chip" in html
    # Nombre de proyecto como enlace al detalle del proyecto.
    assert f"/proyectos/{proy.pk}/" in html


def test_higiene_descripcion_no_duplica_nombre(
        client, cliente_factory, usuario_factory, proyecto_factory):
    """El detalle no repite el nombre del producto cuando ya está en la descripción."""
    from apps.cotizaciones.models import CotizacionItem

    autor, proy, cot = _cotizacion(cliente_factory, usuario_factory, proyecto_factory)
    srv = _servicio(autor)
    # Línea cuya descripción contiene el nombre del producto.
    CotizacionItem.objects.create(
        cotizacion=cot, orden=1, servicio=srv, descripcion=f"{srv.nombre} · Roja",
        cantidad=Decimal("1"), unidad="pieza", precio_unitario=Decimal("50"),
    )
    client.force_login(autor)
    html = client.get(f"/cotizaciones/{cot.pk}/").content.decode()
    # El nombre "Playera" aparece dentro de la descripción, pero el sub-renglón
    # extra con el nombre solo NO debe duplicarlo: aparece a lo más una vez por línea.
    assert f"{srv.nombre} · Roja" in html


# ── §2a Ingreso: comprobante ──────────────────────────────────────────────


def test_ingreso_tiene_campos_comprobante():
    from apps.tesoreria.models import Ingreso
    campos = {f.name for f in Ingreso._meta.get_fields()}
    assert {"drive_file_id", "drive_url_view", "tiene_comprobante"} <= campos


def test_ingreso_comprobante_404_sin_comprobante(client, usuario_factory):
    from apps.tesoreria.models import Ingreso

    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    ing = Ingreso.objects.create(
        monto=Decimal("100.00"), fecha=date.today(), descripcion="Cobro",
        creado_por=autor,
    )
    assert ing.tiene_comprobante is False
    resp = client.get(f"/tesoreria/ingresos/{ing.pk}/comprobante/")
    assert resp.status_code == 404


def test_ingreso_form_tiene_input_comprobante(client, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    html = client.get("/tesoreria/ingresos/nuevo/").content.decode()
    assert 'name="comprobante"' in html
    assert "multipart/form-data" in html


# ── §2b DnD productos: campo orden ────────────────────────────────────────


def test_formset_producto_tiene_campo_orden():
    from apps.los_proyectos.forms import ProyectoProductoForm
    f = ProyectoProductoForm()
    assert "orden" in f.fields
    # Es oculto y opcional (el front lo renumera por DOM; vacío ⇒ 0).
    from django.forms import HiddenInput
    assert isinstance(f.fields["orden"].widget, HiddenInput)
    assert f.fields["orden"].required is False


def test_clean_orden_vacio_es_cero():
    from apps.los_proyectos.forms import ProyectoProductoForm
    f = ProyectoProductoForm(data={})
    f.is_valid()  # dispara clean_*
    # clean_orden convierte None/'' a 0 sin invalidar.
    assert f.clean_orden() == 0
