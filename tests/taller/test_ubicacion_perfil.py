"""S-Cliente-Ubicacion — última ubicación (de visitas) + dirección fiscal con
check en los perfiles de cliente y proveedor."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _visita_geo(usuario, *, cliente=None, proveedor=None, lat=19.43, lng=-99.13):
    from apps.checador.models import Visita
    return Visita.objects.create(
        usuario=usuario, cliente=cliente, proveedor=proveedor,
        tipo="cliente" if cliente else "proveedor",
        registrado_en=timezone.make_aware(datetime.datetime(2026, 6, 9, 12, 0)),
        lat=lat, lng=lng, sin_geo=False,
    )


def test_ultima_ubicacion_de_cliente(usuario_factory, cliente_factory):
    from apps.checador import services
    u = usuario_factory(rol="disenador")
    c = cliente_factory(creado_por=u)
    # una sin geo (se ignora) y una con geo (la última)
    _visita_geo(u, cliente=c)
    from apps.checador.models import Visita
    Visita.objects.create(usuario=u, cliente=c, tipo="cliente",
                          registrado_en=timezone.now(), sin_geo=True)
    v = services.ultima_ubicacion_de(cliente=c)
    assert v is not None and v.lat == 19.43


def test_cliente_form_guarda_fiscal(usuario_factory, cliente_factory):
    from apps.la_cartera.forms import ClienteForm
    c = cliente_factory(creado_por=usuario_factory(rol="super_admin"))
    form = ClienteForm({
        "razon_social": c.razon_social, "rfc": "", "estado": "activo",
        "direccion": "Calle 1", "fiscal_igual": "", "direccion_fiscal": "Calle Fiscal 9",
        "notas": "",
    }, instance=c)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.fiscal_igual is False
    assert obj.direccion_fiscal == "Calle Fiscal 9"


def test_proveedor_form_guarda_fiscal(usuario_factory):
    from apps.el_catalogo.forms import ProveedorForm
    form = ProveedorForm({
        "razon_social": "Prov SA", "nombre_contacto": "", "email_contacto": "",
        "telefono": "", "rfc": "", "direccion": "Bodega 2",
        "fiscal_igual": "on", "direccion_fiscal": "", "notas": "", "activo": "on",
    })
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.fiscal_igual is True


def test_cliente_detalle_muestra_ubicacion(client, usuario_factory, cliente_factory):
    u = usuario_factory(rol="super_admin")
    c = cliente_factory(creado_por=u)
    _visita_geo(u, cliente=c)
    client.force_login(u)
    resp = client.get(f"/cartera/{c.pk}/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Ubicación y dirección" in body
    assert "📍 Mapa" in body
    assert "Dirección fiscal" in body


def test_proveedor_detalle_muestra_ubicacion(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor
    u = usuario_factory(rol="super_admin")
    p = Proveedor.objects.create(razon_social="Cintas SA", activo=True)
    _visita_geo(u, proveedor=p)
    client.force_login(u)
    resp = client.get(f"/catalogo/proveedores/{p.pk}/")
    assert resp.status_code == 200
    assert "Ubicación y dirección" in resp.content.decode()
