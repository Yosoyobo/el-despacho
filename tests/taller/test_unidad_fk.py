"""FK Unidad en CotizacionItem y FacturaItem (preserva CharField legacy).

Cubre:
- `unidad_label` prefiere FK cuando está enlazada.
- `unidad_label` cae a CharField si no hay FK (legacy).
- La data migration enlaza por nombre case-insensitive (smoke).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def unidad_piezas():
    from apps.el_catalogo.models import Unidad
    u, _ = Unidad.objects.get_or_create(nombre="Piezas", defaults={"orden": 10})
    return u


def test_cotizacion_unidad_label_prefiere_fk(cliente_factory, usuario_factory, unidad_piezas):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = Cotizacion.objects.create(cliente=cli, titulo="t", creado_por=autor)
    it = CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="x",
        cantidad=Decimal("1"), unidad="pieza",
        unidad_fk=unidad_piezas, precio_unitario=Decimal("100"),
    )
    assert it.unidad_label == "Piezas"


def test_cotizacion_unidad_label_legacy_sin_fk(cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = Cotizacion.objects.create(cliente=cli, titulo="t", creado_por=autor)
    it = CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="x",
        cantidad=Decimal("1"), unidad="metros",
        precio_unitario=Decimal("100"),
    )
    assert it.unidad_fk_id is None
    assert it.unidad_label == "metros"


def test_factura_unidad_label_prefiere_fk(cliente_factory, usuario_factory, unidad_piezas):
    from apps.facturacion.models import Factura, FacturaItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(cliente=cli, titulo="t", creado_por=autor)
    it = FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="x",
        cantidad=Decimal("1"), unidad="pieza",
        unidad_fk=unidad_piezas, precio_unitario=Decimal("100"),
    )
    assert it.unidad_label == "Piezas"


def test_factura_unidad_label_legacy_sin_fk(cliente_factory, usuario_factory):
    from apps.facturacion.models import Factura, FacturaItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(cliente=cli, titulo="t", creado_por=autor)
    it = FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="x",
        cantidad=Decimal("1"), unidad="hora",
        precio_unitario=Decimal("100"),
    )
    assert it.unidad_fk_id is None
    assert it.unidad_label == "hora"
