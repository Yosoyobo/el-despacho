"""S-Proyecto-Estados-V1: CRUD de Estados de Proyecto en Gerencia."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def test_lista_super_admin(client, usuario_factory):
    from apps.los_proyectos.models import EstadoProyecto
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/catalogos/estados-proyecto/")
    assert resp.status_code == 200
    # Los 7 base aparecen.
    assert b"Por cotizar" in resp.content
    assert EstadoProyecto.objects.filter(sistema=True).count() >= 7


def test_dueno_sin_acceso(client, usuario_factory):
    dueno = usuario_factory(rol="dueno")
    client.force_login(dueno)
    resp = client.get("/catalogos/estados-proyecto/")
    assert resp.status_code == 403


def test_crear_estado_custom(client, usuario_factory):
    from apps.los_proyectos.models import EstadoProyecto
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-proyecto/nuevo/", data={
        "label": "Revisión interna",
        "color": "#7a5af8",
        "orden": 25,
        "terminal": "",
        "activo": "on",
    })
    assert resp.status_code in (301, 302)
    obj = EstadoProyecto.objects.get(label="Revisión interna")
    assert obj.sistema is False
    assert obj.slug  # auto-derivado del label
    assert obj.color == "#7a5af8"


def test_color_hex_invalido_rechazado(client, usuario_factory):
    from apps.los_proyectos.models import EstadoProyecto
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-proyecto/nuevo/", data={
        "label": "Color malo",
        "color": "badge-brand",  # ya no es válido: debe ser #RRGGBB
        "orden": 26,
        "terminal": "",
        "activo": "on",
    })
    assert resp.status_code == 200  # re-render con error, no redirect
    assert not EstadoProyecto.objects.filter(label="Color malo").exists()


def test_editar_renombra_estado_sistema(client, usuario_factory):
    from apps.los_proyectos.models import EstadoProyecto
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-proyecto/por_cotizar/editar/", data={
        "label": "Por presupuestar",
        "color": "#0ba5ec",
        "orden": 10,
        "terminal": "",
        "activo": "on",
    })
    assert resp.status_code in (301, 302)
    obj = EstadoProyecto.objects.get(slug="por_cotizar")
    assert obj.label == "Por presupuestar"
    assert obj.sistema is True  # sigue siendo sistema


def test_no_borra_estado_sistema(client, usuario_factory):
    from apps.los_proyectos.models import EstadoProyecto
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-proyecto/entregado/borrar/")
    assert resp.status_code in (301, 302)
    assert EstadoProyecto.objects.filter(slug="entregado").exists()


def test_no_borra_si_proyectos_lo_usan(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import EstadoProyecto
    EstadoProyecto.objects.create(
        slug="revision_extra", label="Revisión extra", color="#465fff",
        orden=99, terminal=False, activo=True, sistema=False,
    )
    proyecto_factory(estado="revision_extra")
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-proyecto/revision_extra/borrar/")
    assert resp.status_code in (301, 302)
    assert EstadoProyecto.objects.filter(slug="revision_extra").exists()


def test_borra_custom_sin_uso(client, usuario_factory):
    from apps.los_proyectos.models import EstadoProyecto
    EstadoProyecto.objects.create(
        slug="orphan_x", label="Huérfano", color="#667085",
        orden=99, terminal=False, activo=True, sistema=False,
    )
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-proyecto/orphan_x/borrar/")
    assert resp.status_code in (301, 302)
    assert not EstadoProyecto.objects.filter(slug="orphan_x").exists()
