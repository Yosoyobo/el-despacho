"""S-Finanzas-UX (2026-07): consolidación financiera + UX quirúrgica.

Cubre las features con lógica de servidor: saldos del proyecto, unificación
de captura ingreso/egreso desde el proyecto (modal, sin cliente), botones
rápidos de monto (saldo en la API), append de productos al final, gancho de
vinculación de anticipos, y limpieza de la tarjeta de notificación.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _ingreso(proyecto, monto, descripcion="Pago"):
    from apps.tesoreria.models import Ingreso
    return Ingreso.objects.create(
        proyecto=proyecto, cliente=proyecto.cliente, monto=Decimal(str(monto)),
        subtotal=Decimal(str(monto)), fecha=timezone.localdate(), descripcion=descripcion)


def _servicio(nombre="Producto X", precio=1000):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat = CategoriaServicio.objects.filter(activa=True).first() or CategoriaServicio.objects.create(
        nombre="Cat", color="#465fff", orden=1)
    return Servicio.objects.create(
        nombre=nombre, categoria=cat, precio_base=precio, costo=100, unidad="pieza", activo=True)


def _linea(proyecto, servicio, cantidad=1, precio=1000, orden=0):
    from apps.los_proyectos.models import ProyectoProducto
    return ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=servicio, cantidad=cantidad,
        precio_unitario=Decimal(str(precio)), incluir_en_calculo=True, orden=orden)


# ── B3: saldos del proyecto ──────────────────────────────────────────────────
def test_saldo_por_cobrar_descuenta_ingresos(proyecto_factory):
    p = proyecto_factory(iva_exento=True)          # exento → total = base
    _linea(p, _servicio(), cantidad=1, precio=1000)
    assert p.monto_a_facturar == Decimal("1000.00")
    _ingreso(p, "400.00", "Pago 1")
    assert p.total_cobrado_ingresos == Decimal("400.00")
    assert p.saldo_por_cobrar == Decimal("600.00")
    assert list(p.ingresos_ligados)[0].monto == Decimal("400.00")


def test_saldo_por_pagar_descuenta_egresos(proyecto_factory):
    from apps.tesoreria.models import CentroDeCosto, Egreso
    p = proyecto_factory()
    s = _servicio(precio=1000)
    from apps.los_proyectos.models import ProyectoProducto
    ProyectoProducto.objects.create(proyecto=p, servicio=s, cantidad=1,
                                    precio_unitario=Decimal("1000"),
                                    costo_unitario=Decimal("300"), incluir_en_calculo=True)
    centro = CentroDeCosto.objects.create(nombre="Insumos test")
    Egreso.objects.create(proyecto=p, centro_de_costo=centro, monto=Decimal("120.00"),
                          subtotal=Decimal("120.00"), fecha=timezone.localdate(),
                          descripcion="compra")
    assert p.costo_produccion == Decimal("300.00")
    assert p.saldo_por_pagar == Decimal("180.00")


# ── B2: la API expone los saldos para los botones rápidos ────────────────────
def test_api_proyecto_datos_incluye_saldos(client, usuario_factory, proyecto_factory):
    p = proyecto_factory(iva_exento=True)
    _linea(p, _servicio(), cantidad=1, precio=1000)
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/tesoreria/api/proyecto/{p.pk}/datos/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["saldo_por_cobrar"] == "1000.00"
    assert "saldo_por_pagar" in data


# ── B2: modal de ingreso desde el proyecto oculta el cliente y da el saldo ────
def test_ingreso_modal_desde_proyecto(client, usuario_factory, proyecto_factory):
    p = proyecto_factory(iva_exento=True)
    _linea(p, _servicio(), cantidad=1, precio=1000)
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(
        f"/tesoreria/ingresos/nuevo/?proyecto={p.pk}&desde=proyecto",
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'name="desde" value="proyecto"' in html      # hidden desde
    assert "data-monto-rapido" in html                  # botones rápidos
    assert 'data-saldo="1000.00"' in html               # saldo por cobrar


# ── B3: gancho de vinculación de anticipos ───────────────────────────────────
def test_vincular_ingreso_anticipo(client, usuario_factory, proyecto_factory):
    p = proyecto_factory()
    ing = _ingreso(p, "500", "Pago del cliente")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(
        f"/proyectos/{p.pk}/cotizacion/anticipo/vincular",
        data={"ingreso_id": ing.pk}, HTTP_HX_REQUEST="true",
    )
    assert resp.status_code in (200, 204)
    ing.refresh_from_db()
    assert "Anticipo" in ing.descripcion


def test_anticipo_modal_lista_ingresos_existentes(client, usuario_factory, proyecto_factory):
    p = proyecto_factory()
    _ingreso(p, "500", "Ya pagado")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/proyectos/{p.pk}/cotizacion/anticipo", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Ligar como anticipo" in html


# ── B3: los productos nuevos se agregan al final (append) ─────────────────────
def test_siguiente_orden_producto_es_append(proyecto_factory):
    from apps.los_proyectos.views import _siguiente_orden_producto
    p = proyecto_factory()
    s = _servicio()
    _linea(p, s, orden=3)
    _linea(p, _servicio("Otro"), orden=7)
    assert _siguiente_orden_producto(p) == 8


def test_agregar_producto_modal_append(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    _linea(p, _servicio(), orden=5)
    nuevo_serv = _servicio("Nuevo")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(
        f"/proyectos/{p.pk}/agregar-producto",
        data={"servicio": nuevo_serv.pk, "cantidad": "2"}, HTTP_HX_REQUEST="true",
    )
    assert resp.status_code in (200, 204)
    creado = ProyectoProducto.objects.get(proyecto=p, servicio=nuevo_serv)
    assert creado.orden == 6   # max(5) + 1 → al final


# ── B4: tarjeta de notificación clickeable, sin botón "Abrir →" ──────────────
def test_notif_card_clickeable_sin_boton_abrir():
    from pathlib import Path
    ruta = Path("el-taller/templates/perfil_notificaciones/_historial_items.html")
    src = ruta.read_text(encoding="utf-8")
    assert "data-href" in src
    assert "Abrir →" not in src


# ── B2: el minical fuerza ISO (unlocalize) para no romperse con es-mx ─────────
def test_fecha_minical_usa_unlocalize():
    from pathlib import Path
    src = Path("el-taller/templates/tesoreria/_fecha_minical.html").read_text(encoding="utf-8")
    assert "unlocalize" in src
