"""Tests del lote de feedback LC de julio 2026:

- Facturación: folio F (auto máx+1, "Sin información"), parcialidad 50%,
  cascada cliente→proyecto→cotización, concepto obligatorio.
- Egresos: proveedor obligatorio, liquidar cuenta por pagar.
- Proyectos: archivar (reversible, oculta de listas) y eliminar (super_admin,
  solo sin movimientos).
- Kanban: chips con nombre completo.
- Botón atrás: filtro url_segura.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


# ── Facturación · folio y parcialidad ─────────────────────────────────────


def _factura(cli, autor, **kw):
    from apps.facturacion.models import Factura, FacturaItem
    fac = Factura.objects.create(cliente=cli, concepto=kw.pop("concepto", "Prueba"),
                                 creado_por=autor, **kw)
    FacturaItem.objects.create(factura=fac, descripcion="Playeras", cantidad=10,
                               precio_unitario=Decimal("100.00"))
    return fac


def test_folio_autoasignado_y_correlativo(cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    f1 = _factura(cli, autor)
    f2 = _factura(cli, autor)
    assert f1.folio_numero is not None
    assert f2.folio_numero == f1.folio_numero + 1
    assert f1.folio == f"F{f1.folio_numero}"


def test_folio_display_sin_informacion(cliente_factory, usuario_factory):
    from apps.facturacion.models import Factura, FacturaItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = Factura(cliente=cli, concepto="X", creado_por=autor, folio_numero=None)
    # Forzar guardado sin autoasignar folio (simula factura importada sin folio).
    fac.save()
    Factura.objects.filter(pk=fac.pk).update(folio_numero=None)
    fac.refresh_from_db()
    assert fac.folio_display == "Sin información"


def test_titulo_autollena_desde_concepto(cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor, concepto="Lona gran formato")
    assert fac.titulo == "Lona gran formato"


def test_parcialidad_50_reduce_total_a_la_mitad(cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura(cli, autor)  # 10 × 100 = 1000
    total_full = fac.calcular_totales()["total"]
    fac.porcentaje_a_facturar = Decimal("50")
    fac.save(update_fields=["porcentaje_a_facturar"])
    t = fac.calcular_totales()
    assert t["total"] == (total_full / 2).quantize(Decimal("0.01"))
    assert t["parcialidad_descuento"] == Decimal("500.00")


def test_crear_via_form_requiere_folio(client, cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    # Sin folio → form inválido → 200 (re-render), no crea.
    resp = client.post("/facturacion/nueva/", {
        "cliente": cli.pk, "proyecto": "", "cotizacion_origen": "",
        "concepto": "Algo", "estado": "borrador",
        "fecha_emision": date.today().isoformat(),
        "fecha_vencimiento": date.today().isoformat(),
        "moneda": "MXN", "descuento_global_porcentaje": "0",
        "porcentaje_a_facturar": "100", "notas": "", "terminos": "",
        "items-TOTAL_FORMS": "0", "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
    })
    assert resp.status_code == 200
    from apps.facturacion.models import Factura
    assert Factura.objects.count() == 0


# ── Facturación · cascada de endpoints ────────────────────────────────────


def test_api_cliente_proyectos(client, cliente_factory, usuario_factory, proyecto_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    otro = cliente_factory(creado_por=autor)
    p1 = proyecto_factory(cliente=cli, creado_por=autor, nombre="Uno")
    proyecto_factory(cliente=otro, creado_por=autor, nombre="Ajeno")
    resp = client.get(f"/facturacion/api/cliente/{cli.pk}/proyectos/")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["proyectos"]]
    assert p1.pk in ids
    assert len(ids) == 1  # solo los del cliente elegido


def test_api_cliente_proyectos_excluye_archivados(client, cliente_factory, usuario_factory, proyecto_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    p = proyecto_factory(cliente=cli, creado_por=autor)
    p.archivado = True
    p.save(update_fields=["archivado"])
    resp = client.get(f"/facturacion/api/cliente/{cli.pk}/proyectos/")
    assert resp.json()["proyectos"] == []


def test_api_proyecto_datos_incluye_label_cotizacion(client, cliente_factory, usuario_factory, proyecto_factory):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    proy = proyecto_factory(cliente=cli, creado_por=autor, nombre="Verano")
    cot = Cotizacion.objects.create(cliente=cli, proyecto=proy, titulo="Cot", creado_por=autor)
    CotizacionItem.objects.create(cotizacion=cot, descripcion="X", cantidad=1,
                                  precio_unitario=Decimal("500.00"))
    resp = client.get(f"/facturacion/api/proyecto/{proy.pk}/datos/")
    data = resp.json()
    assert data["cliente_id"] == cli.pk
    assert data["cotizaciones"]
    assert "Verano" in data["cotizaciones"][0]["label"]


# ── Egresos · liquidar cuenta por pagar ───────────────────────────────────


@pytest.fixture
def _cuentas_contables(db):
    """Siembra el catálogo mínimo para que los asientos se generen."""
    from apps.contaduria.models import CuentaContable
    for slot, (codigo, nombre, tipo, nat) in {
        "cxp": ("2.1.01", "Proveedores", "pasivo", "acreedora"),
        "banco": ("1.1.02", "Bancos", "activo", "deudora"),
        "caja": ("1.1.01", "Caja", "activo", "deudora"),
        "egreso_operativo": ("5.1.01", "Gastos", "egreso", "deudora"),
        "reembolsos": ("2.1.03", "Reembolsos", "pasivo", "acreedora"),
    }.items():
        CuentaContable.objects.update_or_create(
            codigo=codigo, defaults=dict(slot=slot, nombre=nombre, tipo=tipo,
                                         naturaleza=nat, activa=True))


def test_liquidar_egreso_pendiente_a_pagado(_cuentas_contables, usuario_factory, monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())
    from apps.tesoreria.models import CentroDeCosto, Egreso
    from apps.tesoreria.services import liquidar_egreso_pendiente
    actor = usuario_factory(rol="super_admin")
    centro, _ = CentroDeCosto.objects.get_or_create(
        slug="insumos-de-proyecto", defaults={"nombre": "Insumos"})
    eg = Egreso.objects.create(monto=Decimal("300.00"), fecha=date.today(),
                               descripcion="Maquila", centro_de_costo=centro,
                               estado_pago="pendiente", metodo="transferencia",
                               creado_por=actor, proveedor_nombre="Prov SA")
    liquidar_egreso_pendiente(eg, estado_destino="pagado", metodo="transferencia",
                              banco_o_caja="banco", fecha=date.today(), actor=actor)
    eg.refresh_from_db()
    assert eg.estado_pago == "pagado"
    assert eg.pagado_desde == "banco"
    # Asiento de pago D cxp / H banco.
    from apps.contaduria.models import Asiento
    assert Asiento.vigentes.filter(referencia_externa=f"tesoreria.egreso.pago:{eg.pk}").exists()


def test_liquidar_rechaza_si_no_pendiente(usuario_factory):
    from apps.tesoreria.models import CentroDeCosto, Egreso
    from apps.tesoreria.services import liquidar_egreso_pendiente
    actor = usuario_factory(rol="super_admin")
    centro = CentroDeCosto.objects.create(nombre="C", slug="c")
    eg = Egreso.objects.create(monto=Decimal("1"), fecha=date.today(), descripcion="x",
                               centro_de_costo=centro, estado_pago="pagado", creado_por=actor)
    with pytest.raises(ValueError):
        liquidar_egreso_pendiente(eg, estado_destino="pagado")


# ── Proyectos · archivar / eliminar ───────────────────────────────────────


def test_archivar_oculta_de_lista(client, usuario_factory, proyecto_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    p = proyecto_factory(creado_por=autor)
    resp = client.post(f"/proyectos/{p.pk}/archivar", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    p.refresh_from_db()
    assert p.archivado is True
    # No aparece en la lista de activos.
    from apps.los_proyectos.models import Proyecto
    assert p not in Proyecto.activos.all()
    assert p in Proyecto.objects.all()


def test_archivar_reversible(client, usuario_factory, proyecto_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    p = proyecto_factory(creado_por=autor)
    client.post(f"/proyectos/{p.pk}/archivar", HTTP_HX_REQUEST="true")
    client.post(f"/proyectos/{p.pk}/archivar", HTTP_HX_REQUEST="true")
    p.refresh_from_db()
    assert p.archivado is False


def test_eliminar_bloqueado_con_movimientos(client, usuario_factory, proyecto_factory, cliente_factory):
    from apps.tesoreria.models import CentroDeCosto, Egreso
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    p = proyecto_factory(creado_por=autor)
    centro = CentroDeCosto.objects.create(nombre="C", slug="c")
    Egreso.objects.create(monto=Decimal("1"), fecha=date.today(), descripcion="x",
                          centro_de_costo=centro, proyecto=p, estado_pago="pagado", creado_por=autor)
    resp = client.post(f"/proyectos/{p.pk}/eliminar", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204  # HX-Redirect al detalle con mensaje de bloqueo
    from apps.los_proyectos.models import Proyecto
    assert Proyecto.objects.filter(pk=p.pk).exists()  # NO se borró


def test_eliminar_permite_sin_movimientos(client, usuario_factory, proyecto_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    p = proyecto_factory(creado_por=autor)
    pk = p.pk
    resp = client.post(f"/proyectos/{pk}/eliminar", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    from apps.los_proyectos.models import Proyecto
    assert not Proyecto.objects.filter(pk=pk).exists()


def test_eliminar_solo_super_admin(client, usuario_factory, proyecto_factory):
    autor = usuario_factory(rol="contador")
    client.force_login(autor)
    p = proyecto_factory(creado_por=usuario_factory(rol="super_admin"))
    resp = client.post(f"/proyectos/{p.pk}/eliminar", HTTP_HX_REQUEST="true")
    assert resp.status_code == 403


# ── Botón atrás ────────────────────────────────────────────────────────────


def test_url_segura_filtro():
    from cuentas.templatetags.forms_helpers import url_segura
    assert url_segura("/proyectos/5/") == "/proyectos/5/"
    assert url_segura("//evil.com") == ""
    assert url_segura("https://evil.com") == ""
    assert url_segura("") == ""
    assert url_segura(None) == ""
