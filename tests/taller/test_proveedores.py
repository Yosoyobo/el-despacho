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


# ── Render LC 2026-06-30: tarjetas + filtro de dos niveles + edición inline ──

@pytest.fixture
def _taxonomia():
    """Dos categorías con un servicio cada una, y un proveedor por categoría."""
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    impr, _ = CategoriaServicio.objects.get_or_create(nombre="ImpresiónTest", defaults={"orden": 200})
    conf, _ = CategoriaServicio.objects.get_or_create(nombre="ConfecciónTest", defaults={"orden": 210})
    srv_serig = Servicio.objects.create(nombre="SerigrafíaTest", categoria=impr, precio_base=100, costo=40)
    srv_telas = Servicio.objects.create(nombre="TelasTest", categoria=conf, precio_base=80, costo=30)
    prov_a = Proveedor.objects.create(razon_social="ImprentaUno", activo=True)
    prov_b = Proveedor.objects.create(razon_social="TextilesDos", activo=True)
    srv_serig.proveedores.add(prov_a)
    srv_telas.proveedores.add(prov_b)
    return {"impr": impr, "conf": conf, "srv_serig": srv_serig, "srv_telas": srv_telas,
            "prov_a": prov_a, "prov_b": prov_b}


def test_filtro_categoria_acota_servicios_y_proveedores(client, usuario_factory, _taxonomia):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get(f"/catalogo/proveedores/?categoria={_taxonomia['impr'].pk}")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Proveedor de Impresión sí, el de Confección no.
    assert "ImprentaUno" in body
    assert "TextilesDos" not in body
    # El 2º filtro (servicios) se acota a la categoría: SerigrafíaTest sí, TelasTest no.
    assert "SerigrafíaTest" in body
    assert "TelasTest" not in body


def test_filtro_servicio_acota_proveedores(client, usuario_factory, _taxonomia):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get(f"/catalogo/proveedores/?servicio={_taxonomia['srv_telas'].pk}")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "TextilesDos" in body
    assert "ImprentaUno" not in body


def test_tarjeta_muestra_stats_de_proyectos(client, usuario_factory, proyecto_factory, _taxonomia):
    """La tarjeta cuenta proyectos ligados al proveedor (vía ProyectoProducto)."""
    from apps.los_proyectos.models import ProyectoProducto
    prov = _taxonomia["prov_a"]
    p = proyecto_factory(nombre="Proy con proveedor")
    ProyectoProducto.objects.create(proyecto=p, servicio=_taxonomia["srv_serig"], proveedor=prov, cantidad=1)
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/catalogo/proveedores/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Proyectos totales" in body
    assert "Proyectos activos" in body


def test_detalle_editable_inline_autosave(client, usuario_factory):
    """El detalle guarda en línea (HTMX) sin desactivar al proveedor."""
    from apps.el_catalogo.models import Proveedor
    u = usuario_factory(rol="super_admin")
    p = Proveedor.objects.create(razon_social="Editable SA", telefono="000", activo=True)
    client.force_login(u)
    # GET → form inline + botón Guardar.
    body = client.get(f"/catalogo/proveedores/{p.pk}/").content.decode()
    assert 'id="form-proveedor"' in body
    assert "Guardar" in body
    # POST HTMX (autosave) → 200 + OOB "✓ Guardado", campo actualizado, sigue activo.
    resp = client.post(
        f"/catalogo/proveedores/{p.pk}/",
        {"razon_social": "Editable SA", "nombre_contacto": "Nuevo Contacto",
         "email_contacto": "", "telefono": "555", "rfc": "",
         "direccion": "", "fiscal_igual": "on", "direccion_fiscal": "", "notas": ""},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    assert "✓ Guardado" in resp.content.decode()
    p.refresh_from_db()
    assert p.nombre_contacto == "Nuevo Contacto"
    assert p.telefono == "555"
    assert p.activo is True  # el autoguardado NO lo desactiva


def test_form_nombre_label_es_nombre():
    from apps.el_catalogo.forms import ProveedorForm
    assert ProveedorForm().fields["razon_social"].label == "Nombre"
