"""Smoke tests del sprint S-UX-Volver: verifica que las páginas principales
del Taller renderizan breadcrumb (partial `_breadcrumb.html`) o boton Volver
en sus templates.

Asercion mínima: el HTML contiene el `<nav aria-label="Ruta"` del partial
breadcrumb o el link "Volver" del page_header. Si una pantalla cambia, la
prueba se cae rapido.
"""

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _tiene_breadcrumb_o_volver(content: bytes) -> bool:
    return (b'aria-label="Ruta"' in content) or (b"Volver" in content)


def test_cartera_lista(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    r = client.get("/cartera/")
    assert r.status_code == 200
    assert _tiene_breadcrumb_o_volver(r.content)


def test_proyectos_lista(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    r = client.get("/proyectos/")
    assert r.status_code == 200
    assert _tiene_breadcrumb_o_volver(r.content)


def test_tesoreria_landing(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    r = client.get("/tesoreria/")
    assert r.status_code == 200
    assert _tiene_breadcrumb_o_volver(r.content)


def test_contaduria_landing(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    r = client.get("/contaduria/")
    assert r.status_code == 200
    assert _tiene_breadcrumb_o_volver(r.content)


def test_cotizaciones_lista(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    r = client.get("/cotizaciones/")
    assert r.status_code == 200
    assert _tiene_breadcrumb_o_volver(r.content)


def test_facturacion_lista(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    r = client.get("/facturacion/")
    assert r.status_code == 200
    assert _tiene_breadcrumb_o_volver(r.content)


def test_recados_chat_bandeja(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    r = client.get("/recados/")
    assert r.status_code == 200
    assert _tiene_breadcrumb_o_volver(r.content)


def test_perfil_notificaciones(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    r = client.get("/perfil/notificaciones/")
    assert r.status_code == 200
    assert _tiene_breadcrumb_o_volver(r.content)


def test_cartera_detalle_tiene_back_url(client, usuario_factory, cliente_factory):
    """El detalle de un cliente debe mostrar el botón Volver del page header."""
    u = usuario_factory(rol="dueno")
    cliente = cliente_factory(creado_por=u)
    client.force_login(u)
    r = client.get(f"/cartera/{cliente.pk}/")
    assert r.status_code == 200
    # El partial _page_header con back_url genera un link con icono flecha
    # + label (en este caso "La Cartera"). Buscamos el `href=` específico.
    assert b'href="/cartera/"' in r.content
    assert b'aria-label="Ruta"' in r.content


def test_partial_page_header_acepta_back_url():
    """Smoke directo del partial: con back_url renderiza link Volver."""
    from django.template.loader import render_to_string
    html = render_to_string(
        "_componentes_tailadmin/_page_header.html",
        {"titulo": "Test", "back_url": "/cartera/", "back_label": "La Cartera"},
    )
    assert "La Cartera" in html
    assert 'href="/cartera/"' in html
    # Sin back_url → no debe aparecer el bloque
    html2 = render_to_string(
        "_componentes_tailadmin/_page_header.html",
        {"titulo": "Test"},
    )
    assert "Volver" not in html2
