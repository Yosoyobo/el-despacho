"""Tests de Las Cotizaciones V1 (S2b.cotizaciones-v1).

Cubre:
- Modelo y propiedades (código correlativo, estado_visible, esta_vencida).
- Cálculos: subtotal, descuento global, impuestos trasladados/retenciones, total.
- Transiciones de estado y errores de transición.
- Permisos (anónimo, diseñador, contador, admin).
- Vistas: lista, detalle, nuevo, editar, duplicar, modales HTMX.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


# ── Fixtures locales ────────────────────────────────────────────────────

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


@pytest.fixture
def cot_borrador(cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = Cotizacion.objects.create(
        cliente=cli,
        titulo="Servicios mayo 2026",
        creado_por=autor,
    )
    CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="Diseño gráfico",
        cantidad=Decimal("2"), unidad="pieza",
        precio_unitario=Decimal("1500.00"),
    )
    CotizacionItem.objects.create(
        cotizacion=cot, orden=1, descripcion="Impresión",
        cantidad=Decimal("1"), unidad="lote",
        precio_unitario=Decimal("500.00"),
    )
    return cot


# ── Modelo y código ─────────────────────────────────────────────────────

def test_codigo_es_correlativo(cot_borrador, cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion
    autor = usuario_factory(rol="dueno")
    cli = cliente_factory(creado_por=autor)
    cot2 = Cotizacion.objects.create(cliente=cli, titulo="Otra", creado_por=autor)
    anio = date.today().year
    assert cot_borrador.codigo.startswith(f"COT-{anio}-")
    assert cot2.codigo.startswith(f"COT-{anio}-")
    assert cot_borrador.codigo != cot2.codigo


def test_estado_visible_vencida(cot_borrador):
    cot_borrador.estado = "enviada"
    cot_borrador.fecha_validez = date.today() - timedelta(days=1)
    cot_borrador.save(update_fields=["estado", "fecha_validez"])
    assert cot_borrador.esta_vencida is True
    assert cot_borrador.estado_visible == "vencida"
    # El estado persistido sigue siendo "enviada".
    cot_borrador.refresh_from_db()
    assert cot_borrador.estado == "enviada"


def test_es_editable_solo_en_borrador(cot_borrador):
    assert cot_borrador.es_editable
    cot_borrador.estado = "enviada"
    assert not cot_borrador.es_editable


# ── Cálculos ────────────────────────────────────────────────────────────

def test_calcular_totales_sin_impuestos(cot_borrador):
    t = cot_borrador.calcular_totales()
    # 2*1500 + 1*500 = 3500
    assert t["subtotal_items"] == Decimal("3500.00")
    assert t["descuento_global"] == Decimal("0.00")
    assert t["total"] == Decimal("3500.00")


def test_calcular_totales_con_descuento_global(cot_borrador):
    cot_borrador.descuento_global_porcentaje = Decimal("10.00")
    cot_borrador.save(update_fields=["descuento_global_porcentaje"])
    t = cot_borrador.calcular_totales()
    assert t["subtotal_items"] == Decimal("3500.00")
    assert t["descuento_global"] == Decimal("350.00")
    assert t["total"] == Decimal("3150.00")


def test_calcular_totales_con_iva_y_retencion(cot_borrador, tasa_iva, tasa_ret_isr):
    from apps.cotizaciones.models import CotizacionImpuesto
    CotizacionImpuesto.objects.create(cotizacion=cot_borrador, tasa=tasa_iva)
    CotizacionImpuesto.objects.create(cotizacion=cot_borrador, tasa=tasa_ret_isr)
    t = cot_borrador.calcular_totales()
    # Base 3500 · IVA 16% = 560 · Ret 10% = 350 · Total = 3500 + 560 - 350 = 3710
    assert t["trasladados"] == Decimal("560.00")
    assert t["retenciones"] == Decimal("350.00")
    assert t["total"] == Decimal("3710.00")


def test_descuento_por_linea(cot_borrador):
    item = cot_borrador.items.first()
    item.descuento_porcentaje = Decimal("50.00")
    item.save(update_fields=["descuento_porcentaje"])
    # Línea 1: 2*1500*0.5 = 1500; Línea 2: 500. Total 2000.
    t = cot_borrador.calcular_totales()
    assert t["subtotal_items"] == Decimal("2000.00")


# ── Transiciones de estado ──────────────────────────────────────────────

def test_marcar_enviada_solo_desde_borrador(cot_borrador, usuario_factory):
    from apps.cotizaciones import services
    actor = usuario_factory(rol="dueno")
    services.marcar_enviada(cot_borrador, actor, email_destino="a@b.com")
    cot_borrador.refresh_from_db()
    assert cot_borrador.estado == "enviada"
    assert cot_borrador.enviada_en is not None
    assert cot_borrador.enviada_a_email == "a@b.com"
    with pytest.raises(ValueError):
        services.marcar_enviada(cot_borrador, actor)


def test_marcar_aprobada_desde_enviada(cot_borrador, usuario_factory):
    from apps.cotizaciones import services
    actor = usuario_factory(rol="dueno")
    services.marcar_enviada(cot_borrador, actor)
    cot_borrador.refresh_from_db()
    services.marcar_aprobada(cot_borrador, actor, nombre="Lic. López",
                             email="l@cli.com", referencia="OC-123")
    cot_borrador.refresh_from_db()
    assert cot_borrador.estado == "aprobada"
    assert cot_borrador.aprobada_por_nombre == "Lic. López"
    assert cot_borrador.referencia_aprobacion == "OC-123"


def test_aprobar_requiere_nombre(cot_borrador, usuario_factory):
    from apps.cotizaciones import services
    actor = usuario_factory(rol="dueno")
    services.marcar_enviada(cot_borrador, actor)
    cot_borrador.refresh_from_db()
    with pytest.raises(ValueError):
        services.marcar_aprobada(cot_borrador, actor, nombre="   ")


def test_rechazar_requiere_motivo(cot_borrador, usuario_factory):
    from apps.cotizaciones import services
    actor = usuario_factory(rol="dueno")
    services.marcar_enviada(cot_borrador, actor)
    cot_borrador.refresh_from_db()
    with pytest.raises(ValueError):
        services.marcar_rechazada(cot_borrador, actor, motivo="")


def test_anular_requiere_motivo(cot_borrador, usuario_factory):
    from apps.cotizaciones import services
    actor = usuario_factory(rol="dueno")
    with pytest.raises(ValueError):
        services.marcar_anulada(cot_borrador, actor, motivo="")
    services.marcar_anulada(cot_borrador, actor, motivo="duplicado")
    cot_borrador.refresh_from_db()
    assert cot_borrador.estado == "anulada"
    assert cot_borrador.anulada_por_id == actor.pk


def test_duplicar_copia_items_e_impuestos(cot_borrador, tasa_iva, usuario_factory):
    from apps.cotizaciones import services
    from apps.cotizaciones.models import CotizacionImpuesto
    CotizacionImpuesto.objects.create(cotizacion=cot_borrador, tasa=tasa_iva)
    actor = usuario_factory(rol="dueno")
    nueva = services.duplicar(cot_borrador, actor)
    assert nueva.pk != cot_borrador.pk
    assert nueva.estado == "borrador"
    assert nueva.items.count() == cot_borrador.items.count()
    assert nueva.impuestos.count() == cot_borrador.impuestos.count()
    assert nueva.titulo.startswith("Copia de ")


# ── Permisos / vistas ───────────────────────────────────────────────────

def test_anonimo_redirige(client):
    resp = client.get("/cotizaciones/")
    assert resp.status_code in (301, 302)


def test_disenador_403(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert client.get("/cotizaciones/").status_code == 403


def test_contador_ve_y_crea(client, usuario_factory, cliente_factory):
    c = usuario_factory(rol="contador")
    cli = cliente_factory(creado_por=c)
    client.force_login(c)
    assert client.get("/cotizaciones/").status_code == 200
    resp = client.post("/cotizaciones/nueva/", {
        "cliente": cli.pk, "proyecto": "",
        "titulo": "Cotización test",
        "fecha_emision": date.today().isoformat(),
        "fecha_validez": (date.today() + timedelta(days=30)).isoformat(),
        "moneda": "MXN", "descuento_global_porcentaje": "0",
        "notas": "", "terminos": "",
        # Inline formset: 1 fila vacía + management
        "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
        "items-0-orden": "0",
        "items-0-descripcion": "Línea de prueba",
        "items-0-cantidad": "1",
        "items-0-unidad": "pieza",
        "items-0-precio_unitario": "1000",
        "items-0-descuento_porcentaje": "0",
        "items-0-servicio": "",
    }, follow=True)
    assert resp.status_code == 200
    from apps.cotizaciones.models import Cotizacion
    assert Cotizacion.objects.filter(titulo="Cotización test").exists()


def test_detalle_renderiza(client, usuario_factory, cot_borrador):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get(f"/cotizaciones/{cot_borrador.pk}/")
    assert resp.status_code == 200
    assert cot_borrador.codigo.encode() in resp.content


def test_contador_no_puede_aprobar(client, usuario_factory, cot_borrador):
    from apps.cotizaciones import services
    admin = usuario_factory(rol="super_admin")
    services.marcar_enviada(cot_borrador, admin)
    c = usuario_factory(rol="contador")
    client.force_login(c)
    resp = client.get(f"/cotizaciones/{cot_borrador.pk}/aprobar/")
    assert resp.status_code == 403


def test_admin_aprueba_via_htmx(client, usuario_factory, cot_borrador):
    from apps.cotizaciones import services
    admin = usuario_factory(rol="dueno")
    services.marcar_enviada(cot_borrador, admin)
    client.force_login(admin)
    resp = client.post(
        f"/cotizaciones/{cot_borrador.pk}/aprobar/",
        {"nombre": "Sr. Cliente", "email": "", "referencia": ""},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect", "").endswith(f"/cotizaciones/{cot_borrador.pk}/")
    cot_borrador.refresh_from_db()
    assert cot_borrador.estado == "aprobada"


def test_editar_solo_borrador(client, usuario_factory, cot_borrador):
    from apps.cotizaciones import services
    admin = usuario_factory(rol="super_admin")
    services.marcar_enviada(cot_borrador, admin)
    client.force_login(admin)
    resp = client.get(f"/cotizaciones/{cot_borrador.pk}/editar/")
    # Redirige al detalle con mensaje de error.
    assert resp.status_code in (301, 302)


def test_kpis_landing(client, usuario_factory, cot_borrador):
    from apps.cotizaciones import services
    admin = usuario_factory(rol="super_admin")
    services.marcar_enviada(cot_borrador, admin)
    client.force_login(admin)
    resp = client.get("/cotizaciones/")
    assert resp.status_code == 200
    # Debe haber 1 enviada visible.
    assert b"Enviadas" in resp.content


def test_anular_oculta_de_vigentes(client, usuario_factory, cot_borrador):
    from apps.cotizaciones import services
    from apps.cotizaciones.models import Cotizacion
    admin = usuario_factory(rol="super_admin")
    services.marcar_anulada(cot_borrador, admin, motivo="test")
    assert Cotizacion.objects.filter(pk=cot_borrador.pk).exists()
    assert not Cotizacion.vigentes.filter(pk=cot_borrador.pk).exists()
