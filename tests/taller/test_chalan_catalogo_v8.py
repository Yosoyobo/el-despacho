"""LC Buzón §8 (#153) — El Chalán: buscar productos (read-only) + editar catálogo.

Decisión Oscar: habilitar (a) herramienta read-only de búsqueda de productos y
(b) edición del catálogo por El Chalán, con gating por permiso.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _accion(payload):
    return SimpleNamespace(payload=payload, entidad_tipo=None, entidad_id=None)


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture
def servicio(db):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat V8")
    return Servicio.objects.create(
        nombre="Playera promocional", categoria=cat,
        precio_base=Decimal("120.00"), costo=Decimal("70.00"), activo=True,
    )


def test_actualizar_servicio_edita_precio(usuario_factory, servicio):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    EJECUTORES["actualizar_servicio"](
        _accion({"servicio": "Playera promocional", "precio_base": 150}), admin, {})
    servicio.refresh_from_db()
    assert float(servicio.precio_base) == 150.0


def test_actualizar_servicio_rechaza_sin_permiso(usuario_factory, servicio):
    from apps.el_dictado.ejecutores import EJECUTORES
    u = usuario_factory(rol="disenador")
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["actualizar_servicio"](
            _accion({"servicio": "Playera promocional", "precio_base": 150}), u, {})


def test_buscar_catalogo_tool(usuario_factory, servicio):
    from apps.el_dictado.herramientas import HERRAMIENTAS, _gate_ok
    admin = usuario_factory(rol="super_admin")
    h = HERRAMIENTAS["buscar_catalogo"]
    assert _gate_ok(h.gating, admin)
    res = h.fn({"texto": "Playera"}, admin)
    assert "Playera promocional" in [p["nombre"] for p in res["productos"]]


def test_actualizar_servicio_en_comandos_del_chalan(usuario_factory):
    from lib.dictado_catalogo import comandos_para
    admin = usuario_factory(rol="super_admin")
    assert "actualizar_servicio" in {c["tipo"] for c in comandos_para(admin)}
