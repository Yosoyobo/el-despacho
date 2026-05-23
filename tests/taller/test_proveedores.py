"""S-LC-Feedback-V3: CRM de Proveedores + M2M con Servicio."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_lista_proveedores_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/catalogo/proveedores/")
    assert resp.status_code == 200


def test_crear_proveedor(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/catalogo/proveedores/nuevo", {
        "razon_social": "Textiles del Norte SA",
        "nombre_contacto": "María López",
        "email_contacto": "ventas@textilesnorte.mx",
        "telefono": "555-1234",
        "rfc": "",
        "direccion": "", "notas": "",
        "activo": "on",
    })
    assert resp.status_code == 302
    assert Proveedor.objects.filter(razon_social="Textiles del Norte SA").exists()


def test_detalle_proveedor_lista_servicios(client, usuario_factory):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    u = usuario_factory(rol="super_admin")
    cat = CategoriaServicio.objects.filter(activa=True).first()
    p = Proveedor.objects.create(razon_social="Proveedor X")
    s = Servicio.objects.create(nombre="Producto Y", categoria=cat, precio_base=100, costo=60)
    s.proveedores.add(p)
    client.force_login(u)
    resp = client.get(f"/catalogo/proveedores/{p.pk}/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Producto Y" in body


def test_archivar_proveedor_toggle(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor
    u = usuario_factory(rol="super_admin")
    p = Proveedor.objects.create(razon_social="Proveedor Z", activo=True)
    client.force_login(u)
    resp = client.post(f"/catalogo/proveedores/{p.pk}/archivar")
    assert resp.status_code == 302
    p.refresh_from_db()
    assert p.activo is False
