"""Hotfix S-Chalanes-UX: filas de tareas clickeables, rename producto,
sugerencia de proveedores con IA."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _ns(texto):
    return SimpleNamespace(texto=texto, provider="anthropic", modelo="x",
                           prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1)


def test_filas_tareas_proyecto_clickeables(client, usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Tarea
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    Tarea.objects.create(proyecto=p, titulo="T1", asignada_a=admin,
                         estado="pendiente", prioridad="media")
    client.force_login(admin)
    body = client.get(f"/proyectos/{p.pk}/").content.decode()
    assert 'data-href="/tareas/' in body


def test_form_producto_dice_producto(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    body = client.get("/catalogo/nuevo").content.decode()
    assert "Nuevo producto" in body
    assert "Guardar producto" in body


def test_sugerir_proveedores_ok(client, monkeypatch, usuario_factory):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio

    import lib.analistas as la
    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Impresión-test")
    prov = Proveedor.objects.create(razon_social="Marmotta Print", creado_por=admin)
    Servicio.objects.create(nombre="Playeras", precio_base=100, categoria=cat, creado_por=admin)
    monkeypatch.setattr(la, "analizar",
                        lambda **kw: _ns(f'[{{"id": {prov.pk}, "motivo": "ya surte impresión"}}]'))
    client.force_login(admin)
    resp = client.post("/catalogo/sugerir-proveedores/",
                       {"nombre": "Playera negra", "descripcion": "algodón"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["sugeridos"][0]["id"] == prov.pk


def test_sugerir_proveedores_descarta_ids_invalidos(client, monkeypatch, usuario_factory):
    from apps.el_catalogo.models import Proveedor

    import lib.analistas as la
    admin = usuario_factory(rol="super_admin")
    Proveedor.objects.create(razon_social="Real", creado_por=admin)
    monkeypatch.setattr(la, "analizar", lambda **kw: _ns('[{"id": 99999, "motivo": "inventado"}]'))
    client.force_login(admin)
    data = client.post("/catalogo/sugerir-proveedores/", {"nombre": "X"}).json()
    assert data["ok"] is True
    assert data["sugeridos"] == []


def test_sugerir_sin_nombre_falla(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    data = client.post("/catalogo/sugerir-proveedores/", {"nombre": ""}).json()
    assert data["ok"] is False
