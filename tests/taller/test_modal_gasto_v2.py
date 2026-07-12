"""LC Buzón §2 — modal «Registrar pago» rediseñado.

Cubre: proveedor de solo lectura (viene del gasto), método/estado como
pastillas con default «Tarjeta empresa», «¿Quién solicitó?» pre-poblado con el
Líder, y la mutación server-side método personal ⇒ estado «Por reembolsar».
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture
def catalogo(db):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Modal Gasto Test")
    serv = Servicio.objects.create(
        nombre="Playeras", categoria=cat,
        precio_base=Decimal("100.00"), costo=Decimal("40.00"), activo=True,
    )
    prov = Proveedor.objects.create(razon_social="Textiles ACME", activo=True)
    return {"serv": serv, "prov": prov}


def _producto(proyecto, catalogo, **kw):
    from apps.los_proyectos.models import ProyectoProducto
    d = dict(
        servicio=catalogo["serv"], cantidad=2,
        precio_unitario=Decimal("100.00"), costo_unitario=Decimal("40.00"),
        incluir_en_calculo=True, proveedor=catalogo["prov"],
    )
    d.update(kw)
    return ProyectoProducto.objects.create(proyecto=proyecto, **d)


def _url(p, pp):
    return f"/proyectos/{p.pk}/gasto/producto/{pp.pk}/registrar-modal"


def test_modal_gasto_get_render(client, usuario_factory, proyecto_factory, catalogo):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    client.force_login(admin)
    resp = client.get(_url(p, pp), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert b"Textiles ACME" in resp.content          # proveedor read-only
    assert b'name="metodo"' in resp.content           # método como radios (pastillas)
    assert b'name="solicitado_por"' in resp.content   # ¿quién solicitó?


def test_modal_gasto_post_personal_por_reembolsar(client, usuario_factory, proyecto_factory, catalogo):
    from apps.tesoreria.models import CentroDeCosto, Egreso
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    client.force_login(admin)
    centro = CentroDeCosto.objects.filter(slug="insumos-de-proyecto").first()
    resp = client.post(_url(p, pp), {
        "fecha": "2026-07-10",
        "centro_de_costo": centro.pk if centro else "",
        "proveedor": catalogo["prov"].pk,   # el hidden del modal read-only
        "metodo": "tarjeta_personal",       # método personal
        "estado_pago": "pagado",            # el back-end debe mutarlo
    }, HTTP_HX_REQUEST="true")
    assert resp.status_code in (204, 302)
    eg = Egreso.objects.filter(proyecto=p, origen="proyecto").order_by("-id").first()
    assert eg is not None
    assert eg.estado_pago == "por_reembolsar"  # mutación server-side
