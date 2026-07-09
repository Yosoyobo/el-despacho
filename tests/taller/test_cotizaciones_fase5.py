"""Fase 5 (LC 2026-07) — Cotizaciones: pills, estado inline, PDF inline, notas."""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _proyecto(cli, autor):
    from apps.los_proyectos.models import Proyecto
    return Proyecto.objects.create(nombre="Museo Interactivo", cliente=cli, creado_por=autor)


def test_lista_pills(client, cliente_factory, usuario_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    resp = client.get("/cotizaciones/")
    assert resp.status_code == 200
    # Pills de estado presentes (sin el buscador de texto viejo).
    assert b"Vigentes" in resp.content
    assert b"Aprobadas" in resp.content


def test_lista_muestra_nombre_proyecto_no_codigo(client, cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = _proyecto(cli, autor)
    Cotizacion.objects.create(cliente=cli, proyecto=proy, titulo="Cot", version=1, creado_por=autor)
    client.force_login(autor)
    resp = client.get("/cotizaciones/")
    assert b"Museo Interactivo" in resp.content


def test_pdf_ver_devuelve_html(client, cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = Cotizacion.objects.create(cliente=cli, titulo="Cot", creado_por=autor)
    client.force_login(autor)
    resp = client.get(f"/cotizaciones/{cot.pk}/ver/")
    assert resp.status_code == 200
    assert b"html" in resp.content.lower()


def test_estado_inline_cambia_estado(client, cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion, estados_cot_activos
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = _proyecto(cli, autor)
    activos = estados_cot_activos()
    if len(activos) < 2:
        pytest.skip("Ciclo de cotización sin estados suficientes")
    cot = Cotizacion.objects.create(
        cliente=cli, proyecto=proy, titulo="Cot", version=1,
        estado=activos[0]["slug"], creado_por=autor,
    )
    destino = activos[1]["slug"]
    client.force_login(autor)
    resp = client.post(f"/cotizaciones/{cot.pk}/estado-inline/", {"estado": destino})
    assert resp.status_code == 200
    cot.refresh_from_db()
    assert cot.estado == destino


def test_estado_inline_funciona_con_version_hermana_anulada(client, cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion, estados_cot_activos
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = _proyecto(cli, autor)
    activos = estados_cot_activos()
    if len(activos) < 2:
        pytest.skip("Ciclo sin estados suficientes")
    # v1 anulada; v2 debe poder cambiar de estado igual.
    Cotizacion.objects.create(cliente=cli, proyecto=proy, titulo="v1", version=1,
                              estado="anulada", creado_por=autor)
    v2 = Cotizacion.objects.create(cliente=cli, proyecto=proy, titulo="v2", version=2,
                                   estado=activos[0]["slug"], creado_por=autor)
    client.force_login(autor)
    resp = client.post(f"/cotizaciones/{v2.pk}/estado-inline/", {"estado": activos[1]["slug"]})
    assert resp.status_code == 200
    v2.refresh_from_db()
    assert v2.estado == activos[1]["slug"]


def test_nota_producto_no_se_copia_a_cotizacion(cliente_factory, usuario_factory):
    from apps.cotizaciones.services import generar_desde_proyecto
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import Proyecto, ProyectoProducto
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = Proyecto.objects.create(nombre="P", cliente=cli, creado_por=autor)
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat")
    serv = Servicio.objects.create(nombre="Lona", categoria=cat, precio_base=Decimal("100"), activo=True)
    ProyectoProducto.objects.create(
        proyecto=proy, servicio=serv, cantidad=1, precio_unitario=Decimal("100"),
        nota="NOTA INTERNA SECRETA", incluir_en_calculo=True,
    )
    cot = generar_desde_proyecto(proy, autor)
    for it in cot.items.all():
        assert "NOTA INTERNA SECRETA" not in it.descripcion
