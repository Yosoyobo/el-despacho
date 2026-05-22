"""Smoke test del Wave 5 (S-TailAdmin-Sweep): modales HTMX.

- Las vistas de confirmación (anular ingreso/egreso, cambiar_estado,
  archivar) devuelven el partial-modal cuando reciben `HX-Request: true`,
  y la página completa cuando no.
- POST con HX-Request termina con HTTP 204 + header `HX-Redirect`.
- POST sin HX-Request redirige como siempre (302).
- `_modal_htmx.html` renderiza con título/cuerpo y trae el atributo
  `data-modal-slot-close` en el botón de cerrar.
"""

import pytest
from apps.la_cartera.models import Cliente
from apps.los_proyectos.models import Proyecto
from apps.tesoreria.models import CentroDeCosto, Egreso, Ingreso
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from cuentas.models.usuario import Usuario

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def admin(db):
    return Usuario.objects.create_user(email="admin@test.mx", password="x", rol="dueno", nombre_completo="Admin")


@pytest.fixture
def cliente(db, admin):
    return Cliente.objects.create(razon_social="ACME", estado="activo", activo=True, creado_por=admin)


@pytest.fixture
def proyecto(db, cliente, admin):
    return Proyecto.objects.create(cliente=cliente, nombre="Test", estado="en_proceso_diseno", creado_por=admin)


@pytest.fixture
def centro(db):
    return CentroDeCosto.objects.create(slug="op", nombre="Operación")


@pytest.fixture
def egreso(db, centro, admin):
    from datetime import date
    return Egreso.objects.create(monto=100, descripcion="x", fecha=date.today(), centro_de_costo=centro, creado_por=admin)


@pytest.fixture
def ingreso(db, admin):
    from datetime import date
    return Ingreso.objects.create(monto=200, descripcion="y", fecha=date.today(), creado_por=admin)


def test_modal_htmx_partial_renderiza():
    h = render_to_string(
        "_componentes_tailadmin/_modal_htmx.html",
        {"titulo": "Confirmar", "cuerpo": mark_safe("<p>¿Seguro?</p>")},
    )
    assert "Confirmar" in h
    assert "¿Seguro?" in h
    assert "data-modal-slot-close" in h
    assert "hidden" not in h.split("flex items-center")[0]
    assert "{#" not in h and "{% comment" not in h


def _hx(client):
    return {"HTTP_HX_REQUEST": "true"}


def test_egreso_anular_get_htmx_devuelve_modal_partial(client, admin, egreso):
    client.force_login(admin)
    r = client.get(f"/tesoreria/egresos/{egreso.pk}/anular/", **_hx(client))
    assert r.status_code == 200
    assert b"data-modal-slot-close" in r.content
    assert b"<html" not in r.content[:100]  # no base layout


def test_egreso_anular_get_sin_htmx_devuelve_pagina_completa(client, admin, egreso):
    client.force_login(admin)
    r = client.get(f"/tesoreria/egresos/{egreso.pk}/anular/")
    assert r.status_code == 200
    assert b"<html" in r.content[:200] or b"<!DOCTYPE" in r.content[:200]


def test_egreso_anular_post_htmx_responde_204_con_hx_redirect(client, admin, egreso):
    client.force_login(admin)
    r = client.post(f"/tesoreria/egresos/{egreso.pk}/anular/", {"motivo": "duplicado"}, **_hx(client))
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect", "").endswith(f"/tesoreria/egresos/{egreso.pk}/")
    egreso.refresh_from_db()
    assert egreso.anulado


def test_ingreso_anular_post_sin_htmx_redirige_302(client, admin, ingreso):
    client.force_login(admin)
    r = client.post(f"/tesoreria/ingresos/{ingreso.pk}/anular/", {"motivo": "error"})
    assert r.status_code == 302
    ingreso.refresh_from_db()
    assert ingreso.anulado


def test_proyecto_cambiar_estado_htmx_devuelve_modal(client, admin, proyecto):
    client.force_login(admin)
    r = client.get(f"/proyectos/{proyecto.pk}/cambiar-estado", **_hx(client))
    assert r.status_code == 200
    assert b"data-modal-slot-close" in r.content
    assert b"hx-post" in r.content


def test_cartera_archivar_get_htmx_devuelve_modal_confirmacion(client, admin, cliente):
    client.force_login(admin)
    r = client.get(f"/cartera/{cliente.pk}/archivar", **_hx(client))
    assert r.status_code == 200
    assert b"data-modal-slot-close" in r.content
    assert b"Archivar" in r.content


def test_cartera_archivar_post_htmx_anula_y_devuelve_204(client, admin, cliente):
    client.force_login(admin)
    r = client.post(f"/cartera/{cliente.pk}/archivar", **_hx(client))
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect", "").endswith(f"/cartera/{cliente.pk}/")
    cliente.refresh_from_db()
    assert not cliente.activo


def test_cartera_archivar_get_sin_htmx_redirige_al_detalle(client, admin, cliente):
    client.force_login(admin)
    r = client.get(f"/cartera/{cliente.pk}/archivar")
    assert r.status_code == 302
    assert r.url.endswith(f"/cartera/{cliente.pk}/")
