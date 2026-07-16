"""Ola 2 CUI (S-Chalan-MCP-V1) — Facturación: ejecutores + registro + gating.

Continúa el hilo comercial. Verifica que facturar-una-cotización, cancelar,
duplicar y ligar factura quedaron expuestos como tools de propuesta (registrados
en `capacidades`, gateados por rol) y que cada ejecutor envuelve su service con
el guardrail de permiso (defensa en profundidad) y las reglas de negocio (no
cancelar una factura con cobros).
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

_CUI_V2 = {
    "crear_factura_desde_cotizacion",
    "cancelar_factura",
    "duplicar_factura",
    "ligar_factura_proyecto",
}


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    """Fuerza ejecución inmediata de transaction.on_commit en tests con db."""
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _factura(cli, autor, *, titulo="Factura test"):
    from apps.facturacion.models import Factura, FacturaItem
    fac = Factura.objects.create(cliente=cli, titulo=titulo, creado_por=autor)
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="X",
        cantidad=Decimal("1"), unidad="pieza", precio_unitario=Decimal("1000.00"),
    )
    return fac


def _cotizacion(cli, autor):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    cot = Cotizacion.objects.create(cliente=cli, titulo="Cot test", creado_por=autor)
    CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="A",
        cantidad=Decimal("1"), precio_unitario=Decimal("1000.00"),
    )
    return cot


# ── Registro + gating ────────────────────────────────────────────────────────


def test_cui_v2_registradas_como_propuesta():
    """Cada acción CUI de Facturación tiene ejecutor y es capacidad propuesta."""
    from apps.el_dictado.ejecutores import EJECUTORES

    import capacidades
    for tipo in _CUI_V2:
        assert tipo in EJECUTORES, f"falta ejecutor {tipo}"
        cap = capacidades.CAPACIDADES.get(tipo)
        assert cap is not None and cap.modo == capacidades.MODO_PROPUESTA, f"falta capacidad {tipo}"


def test_gating_por_rol(usuario_factory):
    """El diseñador NO ve las CUI de Facturación (gating facturación); el admin sí.
    `cancelar_factura` usa el permiso 'cancelar' (distinto de 'crear')."""
    import capacidades
    disenador = usuario_factory(rol="disenador")
    admin = usuario_factory(rol="super_admin", email="admin-cui2@example.com")
    dis = {s["nombre"] for s in capacidades.specs_chat(disenador, modos=("propuesta",))}
    adm = {s["nombre"] for s in capacidades.specs_chat(admin, modos=("propuesta",))}
    assert not (_CUI_V2 & dis)          # el diseñador no ve ninguna
    assert adm >= _CUI_V2               # el super_admin las ve todas


def test_cancelar_factura_gateado_por_permiso_cancelar(usuario_factory, cliente_factory):
    """El ejecutor re-chequea permiso (defensa en profundidad): un rol sin
    permiso de facturación no cancela aunque el LLM lo proponga."""
    from apps.el_dictado.ejecutores import EJECUTORES
    disenador = usuario_factory(rol="disenador")
    autor = usuario_factory(rol="super_admin")
    fac = _factura(cliente_factory(creado_por=autor), autor)
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["cancelar_factura"](
            SimpleNamespace(payload={"codigo": fac.codigo, "motivo": "x"}), disenador, {})


# ── Ejecutores ─────────────────────────────────────────────────────────────────


def test_crear_factura_desde_cotizacion(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.facturacion.models import Factura
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    cot = _cotizacion(cli, admin)
    accion = SimpleNamespace(payload={"codigo": cot.codigo})
    EJECUTORES["crear_factura_desde_cotizacion"](accion, admin, {})
    fac = Factura.objects.get(pk=accion.entidad_id)
    assert accion.entidad_tipo == "factura"
    assert fac.cotizacion_origen_id == cot.pk
    assert fac.estado == "borrador"
    assert fac.items.count() == 1


def test_cancelar_factura(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    fac = _factura(cliente_factory(creado_por=admin), admin)
    EJECUTORES["cancelar_factura"](
        SimpleNamespace(payload={"codigo": fac.codigo, "motivo": "captura duplicada"}), admin, {})
    fac.refresh_from_db()
    assert fac.estado == "cancelada"
    assert fac.motivo_cancelacion == "captura duplicada"


def test_cancelar_factura_requiere_motivo(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    fac = _factura(cliente_factory(creado_por=admin), admin)
    with pytest.raises(ValueError, match="motivo"):
        EJECUTORES["cancelar_factura"](
            SimpleNamespace(payload={"codigo": fac.codigo}), admin, {})


def test_cancelar_factura_con_cobros_falla(usuario_factory, cliente_factory):
    """Guardrail del negocio: una factura con cobros no se cancela (alinea con
    `cancelar_factura_cobrada`, prohibido)."""
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    fac = _factura(cliente_factory(creado_por=admin), admin)
    fac.monto_cobrado = Decimal("500.00")
    fac.save(update_fields=["monto_cobrado"])
    with pytest.raises(ValueError, match="cobros"):
        EJECUTORES["cancelar_factura"](
            SimpleNamespace(payload={"codigo": fac.codigo, "motivo": "x"}), admin, {})
    fac.refresh_from_db()
    assert fac.estado != "cancelada"


def test_duplicar_factura(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.facturacion.models import Factura
    admin = usuario_factory(rol="super_admin")
    fac = _factura(cliente_factory(creado_por=admin), admin, titulo="Original")
    accion = SimpleNamespace(payload={"codigo": fac.codigo})
    EJECUTORES["duplicar_factura"](accion, admin, {})
    nueva = Factura.objects.get(pk=accion.entidad_id)
    assert nueva.pk != fac.pk
    assert nueva.estado == "borrador"
    assert nueva.items.count() == 1
    assert nueva.titulo == "Copia de Original"


def test_ligar_factura_proyecto(usuario_factory, cliente_factory, proyecto_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    fac = _factura(cli, admin)
    proyecto = proyecto_factory(cliente=cli, creado_por=admin)
    EJECUTORES["ligar_factura_proyecto"](
        SimpleNamespace(payload={"codigo": fac.codigo, "proyecto_slug": proyecto.slug}), admin, {})
    fac.refresh_from_db()
    assert fac.proyecto_id == proyecto.pk
