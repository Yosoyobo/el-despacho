"""Tests de La Facturación V1 (S2b.facturacion-v1).

Cubre:
- Modelo y código correlativo FAC-YYYY-NNNN.
- Cálculos (idénticos a Cotización).
- crear_desde_cotizacion clona items+impuestos+vínculo.
- Transiciones de estado: emitir, registrar_cobro, cancelar, duplicar.
- Signal de emisión genera asiento auto_factura_emitida con partida doble.
- Signal de cancelación genera reverso.
- Ingreso con factura usa contracuenta cxc (no ingreso_ventas).
- KPIs.
- Permisos por rol.
- Modal HTMX.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    """Fuerza ejecución inmediata de transaction.on_commit en tests con db."""
    from django.db import transaction as _tx
    monkeypatch.setattr(
        _tx, "on_commit",
        lambda fn, using=None, robust=False: fn(),
    )


@pytest.fixture
def tasa_iva():
    from ajustes.models.tasa import TasaImpositiva
    return TasaImpositiva.objects.create(
        nombre="IVA 16%", porcentaje=Decimal("16.00"),
        tipo="trasladado", aplicable_default=True, activa=True, orden=10,
    )


@pytest.fixture
def tasa_ret_isr():
    from ajustes.models.tasa import TasaImpositiva
    return TasaImpositiva.objects.create(
        nombre="ISR retenido 10%", porcentaje=Decimal("10.00"),
        tipo="retencion", aplicable_default=False, activa=True, orden=20,
    )


def _factura(cliente, *, autor, titulo="Factura mayo", items=None, impuestos=None):
    from apps.facturacion.models import Factura, FacturaImpuesto, FacturaItem
    items = items or [
        {"descripcion": "Servicio", "cantidad": Decimal("1"),
         "precio_unitario": Decimal("1000.00")},
    ]
    fac = Factura.objects.create(cliente=cliente, titulo=titulo, creado_por=autor)
    for i, it in enumerate(items):
        FacturaItem.objects.create(
            factura=fac, orden=i,
            descripcion=it["descripcion"],
            cantidad=it.get("cantidad", Decimal("1")),
            unidad=it.get("unidad", "pieza"),
            precio_unitario=it["precio_unitario"],
            descuento_porcentaje=it.get("descuento", Decimal("0")),
        )
    for tasa in (impuestos or []):
        FacturaImpuesto.objects.create(factura=fac, tasa=tasa)
    return fac


def test_editar_concepto_y_estado_en_cualquier_estado(client, cliente_factory, usuario_factory):
    """S-LC-Buzon: la factura se puede editar (concepto/estado) aunque no sea
    borrador; las líneas quedan intactas (formset no se procesa)."""
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    fac.estado = "emitida"
    fac.save(update_fields=["estado"])
    resp = client.post(f"/facturacion/{fac.pk}/editar/", {
        "cliente": cli.pk, "proyecto": "", "cotizacion_origen": "",
        "titulo": "Factura mayo", "concepto": "Lona gran formato", "estado": "emitida",
        "fecha_emision": fac.fecha_emision.isoformat(),
        "fecha_vencimiento": fac.fecha_vencimiento.isoformat(),
        "moneda": "MXN", "descuento_global_porcentaje": "0",
        "notas": "", "terminos": "",
    })
    assert resp.status_code == 302
    fac.refresh_from_db()
    assert fac.concepto == "Lona gran formato"
    assert fac.items.count() == 1  # líneas intactas


# ── Modelo y código ──────────────────────────────────────────────────────


def test_codigo_correlativo(cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    f1 = _factura(cli, autor=autor)
    f2 = _factura(cli, autor=autor)
    anio = date.today().year
    assert f1.codigo.startswith(f"FAC-{anio}-")
    assert f2.codigo.startswith(f"FAC-{anio}-")
    assert f1.codigo != f2.codigo


def test_calcular_totales_con_iva_y_retencion(cliente_factory, usuario_factory, tasa_iva, tasa_ret_isr):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor, items=[
        {"descripcion": "X", "cantidad": Decimal("2"), "precio_unitario": Decimal("1500.00")},
        {"descripcion": "Y", "cantidad": Decimal("1"), "precio_unitario": Decimal("500.00")},
    ], impuestos=[tasa_iva, tasa_ret_isr])
    t = fac.calcular_totales()
    # Base 3500, IVA 560, ISR 350, total 3710
    assert t["subtotal_items"] == Decimal("3500.00")
    assert t["trasladados"] == Decimal("560.00")
    assert t["retenciones"] == Decimal("350.00")
    assert t["total"] == Decimal("3710.00")


def test_esta_vencida_derivada(cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    fac.estado = "emitida"
    fac.fecha_vencimiento = date.today() - timedelta(days=1)
    fac.save(update_fields=["estado", "fecha_vencimiento"])
    assert fac.esta_vencida is True
    assert fac.estado_visible == "vencida"


# ── crear_desde_cotizacion ────────────────────────────────────────────────


def test_crear_desde_cotizacion_clona(cliente_factory, usuario_factory, tasa_iva):
    from apps.cotizaciones.models import Cotizacion, CotizacionImpuesto, CotizacionItem
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = Cotizacion.objects.create(cliente=cli, titulo="Cot test", creado_por=autor)
    CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="A",
        cantidad=Decimal("1"), precio_unitario=Decimal("1000.00"),
    )
    CotizacionImpuesto.objects.create(cotizacion=cot, tasa=tasa_iva)

    fac = services.crear_desde_cotizacion(cot, autor)
    assert fac.cotizacion_origen_id == cot.pk
    assert fac.cliente_id == cli.pk
    assert fac.items.count() == 1
    assert fac.impuestos.count() == 1
    assert fac.estado == "borrador"


# ── Transiciones ─────────────────────────────────────────────────────────


def test_emitir_solo_desde_borrador(cliente_factory, usuario_factory):
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    services.emitir_factura(fac, autor)
    fac.refresh_from_db()
    assert fac.estado == "emitida"
    with pytest.raises(ValueError):
        services.emitir_factura(fac, autor)


def test_emitir_genera_asiento_partida_doble(cliente_factory, usuario_factory, tasa_iva):
    from apps.contaduria.models import Asiento
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor, items=[
        {"descripcion": "X", "cantidad": Decimal("1"), "precio_unitario": Decimal("1000.00")},
    ], impuestos=[tasa_iva])
    services.emitir_factura(fac, autor)
    asiento = Asiento.vigentes.filter(
        referencia_externa=f"facturacion.factura:{fac.pk}",
        origen="auto_factura_emitida",
    ).first()
    assert asiento is not None
    # Cargos: cxc 1160; Abonos: ingreso 1000 + iva 160 = 1160
    cargos = sum(p.cargo for p in asiento.partidas.all())
    abonos = sum(p.abono for p in asiento.partidas.all())
    assert cargos == abonos == Decimal("1160.00")
    # Verifica los slots correctos
    slots_cargo = {p.cuenta.slot for p in asiento.partidas.filter(cargo__gt=0)}
    slots_abono = {p.cuenta.slot for p in asiento.partidas.filter(abono__gt=0)}
    assert "cxc" in slots_cargo
    assert "ingreso_ventas" in slots_abono
    assert "iva_trasladado" in slots_abono


def test_emitir_idempotente_no_duplica_asiento(cliente_factory, usuario_factory):
    """Al re-emitir el mismo signal (idempotencia por referencia_externa)."""
    from apps.contaduria.models import Asiento
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    services.emitir_factura(fac, autor)
    # Forzar re-save sin cambio de estado — no debe duplicar.
    fac.save()
    asientos = Asiento.vigentes.filter(
        referencia_externa=f"facturacion.factura:{fac.pk}",
    )
    assert asientos.count() == 1


def test_registrar_cobro_parcial(cliente_factory, usuario_factory):
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor, items=[
        {"descripcion": "X", "cantidad": Decimal("1"), "precio_unitario": Decimal("1000.00")},
    ])
    services.emitir_factura(fac, autor)
    services.registrar_cobro(
        fac, monto=Decimal("400"), fecha=date.today(),
        metodo="transferencia", actor=autor,
    )
    fac.refresh_from_db()
    assert fac.estado == "cobrada_parcial"
    assert fac.monto_cobrado == Decimal("400.00")
    assert fac.saldo_pendiente == Decimal("600.00")
    assert fac.cobros.count() == 1


def test_registrar_cobro_total(cliente_factory, usuario_factory):
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    services.emitir_factura(fac, autor)
    total = fac.calcular_totales()["total"]
    services.registrar_cobro(
        fac, monto=total, fecha=date.today(),
        metodo="transferencia", actor=autor,
    )
    fac.refresh_from_db()
    assert fac.estado == "cobrada_total"
    assert fac.saldo_pendiente == Decimal("0.00")


def test_registrar_cobro_excede_saldo_falla(cliente_factory, usuario_factory):
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    services.emitir_factura(fac, autor)
    with pytest.raises(ValueError):
        services.registrar_cobro(
            fac, monto=Decimal("999999"), fecha=date.today(),
            metodo="transferencia", actor=autor,
        )


def test_ingreso_con_factura_usa_cxc_como_contracuenta(cliente_factory, usuario_factory):
    from apps.contaduria.models import Asiento
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    services.emitir_factura(fac, autor)
    services.registrar_cobro(
        fac, monto=Decimal("500"), fecha=date.today(),
        metodo="transferencia", actor=autor,
    )
    cobro = fac.cobros.first()
    asiento = Asiento.vigentes.filter(
        referencia_externa=f"tesoreria.ingreso:{cobro.pk}",
        origen="auto_ingreso",
    ).first()
    assert asiento is not None
    # El abono debe ser cxc (cancelar la cuenta por cobrar)
    abono_partida = asiento.partidas.filter(abono__gt=0).first()
    assert abono_partida.cuenta.slot == "cxc"


def test_cancelar_sin_cobros_genera_reverso(cliente_factory, usuario_factory):
    from apps.contaduria.models import Asiento
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    services.emitir_factura(fac, autor)
    services.cancelar(fac, autor, "duplicada por error")
    reverso = Asiento.vigentes.filter(
        referencia_externa=f"facturacion.factura.cancelacion:{fac.pk}",
        origen="auto_factura_cancelada",
    ).first()
    assert reverso is not None
    cargos = sum(p.cargo for p in reverso.partidas.all())
    abonos = sum(p.abono for p in reverso.partidas.all())
    assert cargos == abonos


def test_cancelar_con_cobros_falla(cliente_factory, usuario_factory):
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    services.emitir_factura(fac, autor)
    services.registrar_cobro(
        fac, monto=Decimal("100"), fecha=date.today(),
        metodo="transferencia", actor=autor,
    )
    fac.refresh_from_db()
    with pytest.raises(ValueError):
        services.cancelar(fac, autor, "intento")


def test_duplicar_crea_borrador_con_items(cliente_factory, usuario_factory, tasa_iva):
    from apps.facturacion import services

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor, items=[
        {"descripcion": "X", "cantidad": Decimal("1"), "precio_unitario": Decimal("100.00")},
        {"descripcion": "Y", "cantidad": Decimal("2"), "precio_unitario": Decimal("200.00")},
    ], impuestos=[tasa_iva])
    nueva = services.duplicar(fac, autor)
    assert nueva.pk != fac.pk
    assert nueva.estado == "borrador"
    assert nueva.items.count() == 2
    assert nueva.impuestos.count() == 1
    assert nueva.titulo.startswith("Copia de ")


# ── Permisos / Vistas ────────────────────────────────────────────────────


def test_disenador_no_accede(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert client.get("/facturacion/").status_code == 403


def test_contador_ve_lista(client, usuario_factory):
    u = usuario_factory(rol="contador")
    client.force_login(u)
    assert client.get("/facturacion/").status_code == 200


def test_modal_emitir_via_htmx(client, cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    client.force_login(autor)
    resp = client.post(
        f"/facturacion/{fac.pk}/emitir/",
        {},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect", "").endswith(f"/facturacion/{fac.pk}/")
    fac.refresh_from_db()
    assert fac.estado == "emitida"


def test_evento_factura_emitida(monkeypatch, cliente_factory, usuario_factory):
    """Verifica que el evento se emite con su payload (con noop fixture activo,
    solo confirmamos que services.emitir_factura llama a `emitir` con el tipo)."""
    capturados = []
    from apps.facturacion import services as fs

    def _capt(evt):
        capturados.append(evt)

    monkeypatch.setattr(fs, "emitir", _capt)
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    fs.emitir_factura(fac, autor)
    tipos = [e.tipo for e in capturados]
    assert "factura.emitida" in tipos


# ── KPIs ─────────────────────────────────────────────────────────────────


def test_kpi_facturas_vencidas(cliente_factory, usuario_factory):
    from apps.facturacion import services
    from apps.taller_home.kpis import _kpi_facturas_vencidas

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor)
    services.emitir_factura(fac, autor)
    fac.refresh_from_db()
    # Marcarla vencida.
    fac.fecha_vencimiento = date.today() - timedelta(days=1)
    fac.save(update_fields=["fecha_vencimiento"])

    res = _kpi_facturas_vencidas(autor)
    assert res["valor"] == 1


def test_kpi_monto_por_cobrar(cliente_factory, usuario_factory):
    from apps.facturacion import services
    from apps.taller_home.kpis import _kpi_monto_por_cobrar

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor=autor, items=[
        {"descripcion": "X", "cantidad": Decimal("1"), "precio_unitario": Decimal("750.00")},
    ])
    services.emitir_factura(fac, autor)
    res = _kpi_monto_por_cobrar(autor)
    assert "750" in res["valor"]
