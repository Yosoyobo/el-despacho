"""S-Chalan-Barrido — ejecutores de CREACIÓN del Chalán + granularidad.

Cubre los ejecutores nuevos (crear_servicio/variacion/proveedor/cotizacion/
factura) y el re-chequeo de permiso que se agregó a los ejecutores básicos
(crear_proyecto/cliente = admin/cartera; registrar_egreso = finanzas).
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _accion(payload):
    return SimpleNamespace(payload=payload, entidad_tipo=None, entidad_id=None)


# ── Catálogo: crear servicio / variación / proveedor ──────────────────────────

def test_crear_servicio_happy(usuario_factory, _on_commit_inmediato):
    from apps.el_catalogo.models import Servicio
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    accion = _accion({"nombre": "Playera promocional", "precio_base": 120, "costo": 70})
    EJECUTORES["crear_servicio"](accion, admin, {})
    srv = Servicio.objects.get(pk=accion.entidad_id)
    assert accion.entidad_tipo == "servicio"
    assert srv.nombre == "Playera promocional"
    assert srv.precio_base == Decimal("120.00")
    assert srv.costo == Decimal("70.00")
    assert srv.categoria_id  # cae a la primera categoría activa


def test_crear_servicio_rechaza_disenador(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["crear_servicio"](_accion({"nombre": "X", "precio_base": 10}), u, {})


def test_crear_servicio_categoria_inexistente(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    with pytest.raises(ValueError, match="Categoría"):
        EJECUTORES["crear_servicio"](
            _accion({"nombre": "X", "precio_base": 10, "categoria": "no-existe-zzz"}), admin, {}
        )


def test_crear_variacion_por_nombre(usuario_factory):
    from apps.el_catalogo.models import CategoriaServicio, Servicio, Variacion
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    cat = CategoriaServicio.objects.filter(activa=True).first()
    srv = Servicio.objects.create(nombre="Lona impresa", categoria=cat, precio_base=Decimal("500"))
    accion = _accion({
        "servicio": "Lona impresa", "nombre": "2x1m · 1 tinta",
        "costo": 200, "impresion_activa": True, "impresion_costo": 50,
    })
    EJECUTORES["crear_variacion"](accion, admin, {})
    var = Variacion.objects.get(pk=accion.entidad_id)
    assert var.servicio_id == srv.pk
    assert var.costo_total == Decimal("250")  # 200 + 50 impresión


def test_crear_variacion_referencia_accion(usuario_factory):
    """Encadenado: crear_servicio (acción 0) + crear_variacion (@accion_0)."""
    from apps.el_catalogo.models import Servicio, Variacion
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    a0 = _accion({"nombre": "Taza sublimada", "precio_base": 90})
    EJECUTORES["crear_servicio"](a0, admin, {})
    contexto = {"entidades_creadas": {0: {"tipo": "servicio", "id": a0.entidad_id}}}
    a1 = _accion({"servicio": "@accion_0", "nombre": "11oz blanca"})
    EJECUTORES["crear_variacion"](a1, admin, contexto)
    var = Variacion.objects.get(pk=a1.entidad_id)
    assert var.servicio_id == Servicio.objects.get(pk=a0.entidad_id).pk


def test_crear_proveedor_happy(usuario_factory, _on_commit_inmediato):
    from apps.el_catalogo.models import Proveedor
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    accion = _accion({"razon_social": "Telas del Norte", "nombre_contacto": "Luis", "telefono": "5559090"})
    EJECUTORES["crear_proveedor"](accion, admin, {})
    prov = Proveedor.objects.get(pk=accion.entidad_id)
    assert prov.razon_social == "Telas del Norte"
    assert accion.entidad_tipo == "proveedor"


def test_crear_proveedor_rechaza_disenador(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["crear_proveedor"](_accion({"razon_social": "X"}), u, {})


# ── Documentos: crear cotización / factura ────────────────────────────────────

def _tasa_iva_default():
    from ajustes.models.tasa import TasaImpositiva
    return TasaImpositiva.objects.create(
        nombre="IVA 16%", porcentaje=Decimal("16.00"), tipo="traslado",
        aplicable_default=True,
    )


def test_crear_cotizacion_happy(usuario_factory, cliente_factory, _on_commit_inmediato):
    from apps.cotizaciones.models import Cotizacion
    from apps.el_dictado.ejecutores import EJECUTORES
    _tasa_iva_default()
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory()
    accion = _accion({
        "cliente_slug": cli.slug, "titulo": "Branding completo",
        "items": [
            {"descripcion": "Diseño de logo", "precio_unitario": 8000},
            {"descripcion": "Manual de marca", "cantidad": 1, "precio_unitario": 4000},
        ],
    })
    EJECUTORES["crear_cotizacion"](accion, admin, {})
    cot = Cotizacion.objects.get(pk=accion.entidad_id)
    assert cot.estado == "borrador"
    assert cot.codigo.startswith("COT-")
    assert cot.items.count() == 2
    assert cot.impuestos.count() == 1  # IVA default aplicado
    totales = cot.calcular_totales()
    assert totales["subtotal_items"] == Decimal("12000.00")
    assert totales["total"] == Decimal("13920.00")  # +16% IVA


def test_crear_cotizacion_rechaza_sin_items(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory()
    with pytest.raises(ValueError, match="línea"):
        EJECUTORES["crear_cotizacion"](
            _accion({"cliente_slug": cli.slug, "titulo": "X", "items": []}), admin, {}
        )


def test_crear_cotizacion_rechaza_disenador(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    cli = cliente_factory()
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["crear_cotizacion"](
            _accion({"cliente_slug": cli.slug, "titulo": "X",
                     "items": [{"descripcion": "a", "precio_unitario": 1}]}), u, {}
        )


def test_crear_factura_happy(usuario_factory, cliente_factory, _on_commit_inmediato):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.facturacion.models import Factura
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory()
    accion = _accion({
        "cliente_slug": cli.slug, "titulo": "Servicios de diseño",
        "items": [{"descripcion": "Diseño de menú", "precio_unitario": 4500}],
        "impuestos": [],  # sin impuestos para simplificar
    })
    EJECUTORES["crear_factura"](accion, admin, {})
    fac = Factura.objects.get(pk=accion.entidad_id)
    assert fac.estado == "borrador"
    assert fac.codigo.startswith("FAC-")
    assert fac.items.count() == 1
    assert fac.calcular_totales()["total"] == Decimal("4500.00")


# ── Granularidad de los ejecutores básicos (re-chequeo de permiso) ────────────

def test_registrar_egreso_rechaza_disenador(usuario_factory):
    """Gap crítico cerrado: registrar_egreso escribe dinero y antes no gateaba."""
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["registrar_egreso"](
            _accion({"monto": 100, "descripcion": "x", "centro_de_costo_slug": "otros"}), u, {}
        )


def test_crear_proyecto_rechaza_disenador(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    cli = cliente_factory()
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["crear_proyecto"](
            _accion({"nombre": "X", "cliente_slug": cli.slug}), u, {}
        )


def test_crear_cliente_rechaza_disenador(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["crear_cliente"](_accion({"razon_social": "X"}), u, {})
