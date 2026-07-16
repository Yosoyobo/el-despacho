"""Ola 1 CUI (S-Chalan-MCP-V1 commit 4): ejecutores nuevos + registro + gating.

Verifica que los huecos de "lo que se hace con clicks" quedaron expuestos como
tools de propuesta (registrados en `capacidades`, gateados por rol) y que los
ejecutores de archivar (soft-delete reversible) funcionan sin borrar.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

_CUI = {
    "duplicar_proyecto", "quitar_producto_proyecto", "archivar_proyecto",
    "archivar_cliente", "archivar_tarea", "cambiar_estado_mandado",
    "duplicar_cotizacion", "generar_factura_anticipo",
}


def test_cui_acciones_registradas_como_propuesta():
    """Cada acción CUI tiene ejecutor y es una capacidad modo=propuesta."""
    from apps.el_dictado.ejecutores import EJECUTORES

    import capacidades
    for tipo in _CUI:
        assert tipo in EJECUTORES, f"falta ejecutor {tipo}"
        cap = capacidades.CAPACIDADES.get(tipo)
        assert cap is not None and cap.modo == capacidades.MODO_PROPUESTA, f"falta capacidad {tipo}"


def test_gating_cui_por_rol(usuario_factory):
    """Un diseñador NO ve las CUI gateadas (admin/facturación); el super_admin sí."""
    import capacidades
    disenador = usuario_factory(rol="disenador")
    admin = usuario_factory(rol="super_admin", email="admin-cui@example.com")
    dis = {s["nombre"] for s in capacidades.specs_chat(disenador, modos=("propuesta",))}
    adm = {s["nombre"] for s in capacidades.specs_chat(admin, modos=("propuesta",))}
    assert "duplicar_proyecto" not in dis        # gating admin
    assert "generar_factura_anticipo" not in dis  # gating facturacion_crear
    assert {"duplicar_proyecto", "generar_factura_anticipo"} <= adm


def test_archivar_proyecto_es_reversible(usuario_factory, proyecto_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    EJECUTORES["archivar_proyecto"](SimpleNamespace(payload={"proyecto_slug": p.slug}), admin, {})
    p.refresh_from_db()
    assert p.archivado is True and p.archivado_por_id == admin.pk
    EJECUTORES["archivar_proyecto"](
        SimpleNamespace(payload={"proyecto_slug": p.slug, "restaurar": True}), admin, {})
    p.refresh_from_db()
    assert p.archivado is False and p.archivado_por_id is None


def test_archivar_cliente_soft_delete(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    c = cliente_factory(creado_por=admin)
    EJECUTORES["archivar_cliente"](SimpleNamespace(payload={"cliente_slug": c.slug}), admin, {})
    c.refresh_from_db()
    assert c.activo is False  # oculto de listas, NO borrado
    EJECUTORES["archivar_cliente"](
        SimpleNamespace(payload={"cliente_slug": c.slug, "restaurar": True}), admin, {})
    c.refresh_from_db()
    assert c.activo is True


def test_archivar_tarea(usuario_factory, proyecto_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.el_pizarron.models.tarea import Tarea
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="revisar arte")
    EJECUTORES["archivar_tarea"](SimpleNamespace(payload={"tarea_id": t.pk}), admin, {})
    t.refresh_from_db()
    assert t.archivada is True
