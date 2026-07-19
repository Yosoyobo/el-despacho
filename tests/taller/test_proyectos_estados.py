"""S-Proyecto-Estados-V1: modelo EstadoProyecto + dropdown inline +
card Proveedores aplicables en el detalle del proyecto."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_seed_carga_7_estados_base():
    from apps.los_proyectos.models import EstadoProyecto
    slugs = set(EstadoProyecto.objects.values_list("slug", flat=True))
    assert {
        "por_cotizar",
        "esperando_respuesta",
        "en_proceso_diseno",
        "en_proceso_produccion",
        "entregado",
        "en_pausa",
        "cancelado",
    } <= slugs
    # Los 7 base están marcados sistema=True.
    sistema = EstadoProyecto.objects.filter(sistema=True).count()
    assert sistema >= 7


def test_entregado_es_terminal_y_por_cotizar_no(proyecto_factory):
    p_entregado = proyecto_factory(estado="entregado")
    p_borrador = proyecto_factory(estado="por_cotizar")
    assert p_entregado.es_terminal is True
    assert p_borrador.es_terminal is False


def test_get_estado_display_lee_del_modelo(proyecto_factory):
    from apps.los_proyectos.models import EstadoProyecto
    EstadoProyecto.objects.filter(slug="por_cotizar").update(label="Por presupuestar")
    p = proyecto_factory(estado="por_cotizar")
    assert p.get_estado_display() == "Por presupuestar"


def test_dropdown_inline_cambia_estado(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="por_cotizar")
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/cambiar-estado",
        data={"estado": "en_proceso_diseno"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    p.refresh_from_db()
    assert p.estado == "en_proceso_diseno"
    # Devuelve partial con el dropdown actualizado.
    assert b"En proceso de dise" in resp.content


def test_diseñador_no_puede_cambiar_estado(client, usuario_factory, proyecto_factory):
    diseñador = usuario_factory(rol="disenador")
    p = proyecto_factory(estado="por_cotizar")
    client.force_login(diseñador)
    resp = client.post(
        f"/proyectos/{p.pk}/cambiar-estado",
        data={"estado": "entregado"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 403
    p.refresh_from_db()
    assert p.estado == "por_cotizar"


# Nota (ticket UX 2026-07): el recuadro "Proveedores aplicables" se retiró del
# detalle del proyecto (la info relevante ya vive en el panel de Proveedores de
# arriba). El test que lo verificaba se eliminó con la feature.


def test_proveedor_inactivo_no_aparece(client, usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import (
        CategoriaServicio,
        Proveedor,
        Servicio,
    )
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Diseño", defaults={"orden": 10})
    serv = Servicio.objects.create(nombre="Logo", categoria=cat, precio_base=1000, activo=True)
    prov_inactivo = Proveedor.objects.create(razon_social="ZombieCo", activo=False)
    serv.proveedores.add(prov_inactivo)
    ProyectoProducto.objects.create(proyecto=p, servicio=serv, cantidad=1)

    client.force_login(admin)
    resp = client.get(f"/proyectos/{p.pk}/")
    assert resp.status_code == 200
    assert b"ZombieCo" not in resp.content


def test_estados_disponibles_solo_activos_en_dropdown(
    client, usuario_factory, proyecto_factory
):
    from apps.los_proyectos.models import EstadoProyecto
    EstadoProyecto.objects.filter(slug="en_pausa").update(activo=False)
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    client.force_login(admin)
    resp = client.get(f"/proyectos/{p.pk}/")
    assert resp.status_code == 200
    # El option de "en_pausa" no aparece en el select.
    assert b'value="en_pausa"' not in resp.content
    assert b'value="por_cotizar"' in resp.content
