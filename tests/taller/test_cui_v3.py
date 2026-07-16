"""Ola 3 CUI (S-Chalan-MCP-V1) — completar verbos: anular + editar.

Verifica que los verbos que le faltaban al Chalán —anular (cotización, movimiento
contable) y editar (proveedor, variación)— quedaron expuestos como tools de
propuesta (registrados en `capacidades`, gateados por rol) y que cada ejecutor
envuelve su lógica con el guardrail de permiso (defensa en profundidad).
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

_CUI_V3 = {
    "anular_cotizacion",
    "anular_asiento",
    "actualizar_proveedor",
    "actualizar_variacion",
}


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _cotizacion(cli, autor):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    cot = Cotizacion.objects.create(cliente=cli, titulo="Cot test", creado_por=autor)
    CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="A",
        cantidad=Decimal("1"), precio_unitario=Decimal("1000.00"),
    )
    return cot


def _servicio_con_variacion(autor):
    from apps.el_catalogo.models import CategoriaServicio, Servicio, Variacion
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Diseño", defaults={"orden": 10})
    srv = Servicio.objects.create(nombre="Playera", precio_base="120.00", categoria=cat, creado_por=autor)
    var = Variacion.objects.create(servicio=srv, nombre="Talla M", costo=Decimal("70.00"))
    return srv, var


# ── Registro + gating ────────────────────────────────────────────────────────


def test_cui_v3_registradas_como_propuesta():
    from apps.el_dictado.ejecutores import EJECUTORES

    import capacidades
    for tipo in _CUI_V3:
        assert tipo in EJECUTORES, f"falta ejecutor {tipo}"
        cap = capacidades.CAPACIDADES.get(tipo)
        assert cap is not None and cap.modo == capacidades.MODO_PROPUESTA, f"falta capacidad {tipo}"


def test_gating_por_rol(usuario_factory):
    """El diseñador NO ve las CUI (anular comercial-contable / editar catálogo);
    el super_admin sí (tiene todos los permisos)."""
    import capacidades
    disenador = usuario_factory(rol="disenador")
    admin = usuario_factory(rol="super_admin", email="admin-cui3@example.com")
    dis = {s["nombre"] for s in capacidades.specs_chat(disenador, modos=("propuesta",))}
    adm = {s["nombre"] for s in capacidades.specs_chat(admin, modos=("propuesta",))}
    assert not (_CUI_V3 & dis)
    assert adm >= _CUI_V3


def test_anular_asiento_gateado_por_permiso(usuario_factory):
    """Defensa en profundidad: un rol sin permiso de contaduría no anula."""
    from apps.el_dictado.ejecutores import EJECUTORES
    disenador = usuario_factory(rol="disenador")
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["anular_asiento"](
            SimpleNamespace(payload={"codigo": "AST-2026-0001", "motivo": "x"}), disenador, {})


# ── Ejecutores ─────────────────────────────────────────────────────────────────


def test_anular_cotizacion(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=admin), admin)
    EJECUTORES["anular_cotizacion"](
        SimpleNamespace(payload={"codigo": cot.codigo, "motivo": "el cliente desistió"}), admin, {})
    cot.refresh_from_db()
    assert cot.estado == "anulada"
    assert cot.motivo_anulacion == "el cliente desistió"


def test_anular_cotizacion_requiere_motivo(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=admin), admin)
    with pytest.raises(ValueError, match="motivo"):
        EJECUTORES["anular_cotizacion"](
            SimpleNamespace(payload={"codigo": cot.codigo}), admin, {})


def test_anular_asiento(usuario_factory):
    from apps.contaduria import services
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    asiento = services.crear_asiento(
        descripcion="Movimiento de prueba",
        partidas=[
            {"cuenta": "1.1.02", "cargo": Decimal("500.00")},
            {"cuenta": "4.1.01", "abono": Decimal("500.00")},
        ],
        creado_por=admin,
    )
    EJECUTORES["anular_asiento"](
        SimpleNamespace(payload={"codigo": asiento.codigo, "motivo": "captura duplicada"}), admin, {})
    asiento.refresh_from_db()
    assert asiento.anulado is True
    assert asiento.motivo_anulacion == "captura duplicada"


def test_actualizar_proveedor(usuario_factory):
    from apps.el_catalogo.models import Proveedor
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social="Telas del Norte", creado_por=admin)
    EJECUTORES["actualizar_proveedor"](
        SimpleNamespace(payload={"proveedor": "Telas del Norte", "telefono": "555-9090"}), admin, {})
    prov.refresh_from_db()
    assert prov.telefono == "555-9090"


def test_actualizar_proveedor_requiere_cambios(usuario_factory):
    from apps.el_catalogo.models import Proveedor
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    Proveedor.objects.create(razon_social="Telas del Norte", creado_por=admin)
    with pytest.raises(ValueError, match="cambiar"):
        EJECUTORES["actualizar_proveedor"](
            SimpleNamespace(payload={"proveedor": "Telas del Norte"}), admin, {})


def test_actualizar_variacion_por_id(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    _srv, var = _servicio_con_variacion(admin)
    EJECUTORES["actualizar_variacion"](
        SimpleNamespace(payload={"variacion_id": var.pk, "costo": "90"}), admin, {})
    var.refresh_from_db()
    assert var.costo == Decimal("90.00")


def test_actualizar_variacion_por_servicio_y_nombre(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    _srv, var = _servicio_con_variacion(admin)
    EJECUTORES["actualizar_variacion"](
        SimpleNamespace(payload={"servicio": "Playera", "variacion": "Talla M", "disponible": False}), admin, {})
    var.refresh_from_db()
    assert var.disponible is False
