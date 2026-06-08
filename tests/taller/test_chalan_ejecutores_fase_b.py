"""Fase B (S-Chalán-Scope-OCR) — ejecutores de escritura financiera del Chalán.

Cada ejecutor financiero gatea por permiso (regla #2) y envuelve un servicio
existente. Aquí se ejercita el gating + el happy-path de cada uno llamando al
ejecutor directamente con una acción simulada.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def _on_commit_inmediato(monkeypatch):
    """Bug E §14: fuerza transaction.on_commit a correr dentro del rollback."""
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _accion(payload):
    return SimpleNamespace(payload=payload, entidad_tipo=None, entidad_id=None)


def _factura_borrador(cliente, autor, total="1000.00"):
    from apps.facturacion.models import Factura, FacturaItem
    fac = Factura.objects.create(cliente=cliente, titulo="Factura prueba", creado_por=autor)
    FacturaItem.objects.create(
        factura=fac, descripcion="Servicio", cantidad=1,
        precio_unitario=Decimal(total),
    )
    return fac


# ── Gating por permiso (defensa en profundidad) ───────────────────────────────

def test_emitir_factura_rechaza_disenador(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    cli = cliente_factory()
    fac = _factura_borrador(cli, usuario_factory(rol="super_admin"))
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["emitir_factura"](_accion({"codigo": fac.codigo}), u, {})


def test_capturar_traspaso_rechaza_disenador(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["capturar_traspaso"](
            _accion({"cuenta_origen": "banco", "cuenta_destino": "caja", "monto": 100}), u, {}
        )


def test_comandos_para_filtra_financieras(usuario_factory):
    from lib.dictado_catalogo import comandos_para
    diseñador = usuario_factory(rol="disenador")
    tipos = {c["tipo"] for c in comandos_para(diseñador)}
    assert "emitir_factura" not in tipos
    assert "crear_proyecto" in tipos  # las abiertas sí
    admin = usuario_factory(rol="super_admin")
    tipos_admin = {c["tipo"] for c in comandos_para(admin)}
    assert {"emitir_factura", "cobrar_factura", "capturar_traspaso"} <= tipos_admin


# ── Happy path ────────────────────────────────────────────────────────────────

def test_registrar_ingreso(usuario_factory, _on_commit_inmediato):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.tesoreria.models import Ingreso
    admin = usuario_factory(rol="super_admin")
    accion = _accion({"monto": "5000", "descripcion": "Anticipo", "metodo": "transferencia"})
    EJECUTORES["registrar_ingreso"](accion, admin, {})
    assert accion.entidad_tipo == "ingreso"
    ing = Ingreso.objects.get(pk=accion.entidad_id)
    assert ing.monto == Decimal("5000.00")
    assert ing.codigo.startswith("ING-")


def test_emitir_factura(usuario_factory, cliente_factory, _on_commit_inmediato):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.facturacion.models import Factura
    admin = usuario_factory(rol="super_admin")
    fac = _factura_borrador(cliente_factory(), admin)
    EJECUTORES["emitir_factura"](_accion({"codigo": fac.codigo}), admin, {})
    fac = Factura.objects.get(pk=fac.pk)
    assert fac.estado == "emitida"


def test_cobrar_factura_parcial(usuario_factory, cliente_factory, _on_commit_inmediato):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.facturacion.models import Factura
    from apps.facturacion.services import emitir_factura
    admin = usuario_factory(rol="super_admin")
    fac = _factura_borrador(cliente_factory(), admin, total="1000.00")
    emitir_factura(fac, admin)
    EJECUTORES["cobrar_factura"](
        _accion({"codigo": fac.codigo, "monto": "400", "metodo": "transferencia"}), admin, {}
    )
    fac = Factura.objects.get(pk=fac.pk)
    assert fac.estado == "cobrada_parcial"
    assert fac.monto_cobrado == Decimal("400.00")


def test_enviar_cotizacion(usuario_factory, cliente_factory, _on_commit_inmediato):
    from apps.cotizaciones.models import Cotizacion
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    cot = Cotizacion.objects.create(cliente=cliente_factory(), titulo="Cot", creado_por=admin)
    EJECUTORES["enviar_cotizacion"](_accion({"codigo": cot.codigo}), admin, {})
    cot = Cotizacion.objects.get(pk=cot.pk)
    assert cot.estado == "enviada"


def test_capturar_traspaso(usuario_factory, _on_commit_inmediato):
    from apps.contaduria.models import Asiento
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    accion = _accion({"cuenta_origen": "banco", "cuenta_destino": "caja",
                      "monto": "750", "descripcion": "Retiro a caja chica"})
    EJECUTORES["capturar_traspaso"](accion, admin, {})
    assert accion.entidad_tipo == "asiento"
    asiento = Asiento.objects.get(pk=accion.entidad_id)
    assert asiento.partidas.count() == 2


def test_reembolsar_egreso_valida_estado(usuario_factory, _on_commit_inmediato):
    """Un egreso que no está 'por_reembolsar' es rechazado con mensaje claro."""
    from datetime import date

    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.tesoreria.models import CentroDeCosto, Egreso
    admin = usuario_factory(rol="super_admin")
    centro = CentroDeCosto.objects.filter(activo=True).first()
    eg = Egreso.objects.create(
        monto=Decimal("100"), descripcion="Gasto", centro_de_costo=centro,
        estado_pago="pagado", metodo="transferencia", fecha=date.today(),
        creado_por=admin,
    )
    with pytest.raises(ValueError, match="reembolsar"):
        EJECUTORES["reembolsar_egreso"](_accion({"codigo": eg.codigo}), admin, {})
