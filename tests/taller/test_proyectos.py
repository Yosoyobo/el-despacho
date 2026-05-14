"""Tests de vistas de Los Proyectos."""

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_anonimo_redirigido(client):
    resp = client.get("/proyectos/")
    assert resp.status_code in (301, 302)


def test_admin_ve_todos(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    proyecto_factory()
    proyecto_factory()
    client.force_login(admin)
    resp = client.get("/proyectos/")
    assert resp.status_code == 200


def test_disenador_ve_solo_asignados(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoAsignacion

    d = usuario_factory(rol="disenador")
    p1 = proyecto_factory(nombre="Asignado")
    proyecto_factory(nombre="No-asignado")
    ProyectoAsignacion.objects.create(proyecto=p1, usuario=d, rol_en_proyecto="disenador")
    client.force_login(d)
    resp = client.get("/proyectos/")
    assert resp.status_code == 200
    contenido = resp.content.decode()
    assert "Asignado" in contenido
    assert "No-asignado" not in contenido


def test_contador_ve_todos(client, usuario_factory, proyecto_factory):
    c = usuario_factory(rol="contador")
    proyecto_factory(nombre="Proyecto X")
    client.force_login(c)
    resp = client.get("/proyectos/")
    assert resp.status_code == 200
    assert "Proyecto X" in resp.content.decode()


def test_disenador_no_crea_proyecto(client, usuario_factory):
    d = usuario_factory(rol="disenador")
    client.force_login(d)
    assert client.get("/proyectos/nuevo").status_code == 403


def test_admin_crea_proyecto(client, usuario_factory, cliente_factory):
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    client.force_login(admin)
    resp = client.post(
        "/proyectos/nuevo",
        {"nombre": "Catálogo 2026", "cliente": cli.pk, "descripcion": "",
         "estado": "prospecto", "fecha_inicio": "", "fecha_compromiso": "", "monto_estimado": ""},
        follow=True,
    )
    assert resp.status_code == 200
    from apps.los_proyectos.models import Proyecto
    assert Proyecto.objects.filter(nombre="Catálogo 2026").exists()


def test_cambiar_estado_emite_evento(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="dueno")
    p = proyecto_factory(estado="cotizado")
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/cambiar-estado",
        {"estado": "en_diseno"},
        follow=True,
    )
    assert resp.status_code == 200
    p.refresh_from_db()
    assert p.estado == "en_diseno"


def test_detalle_403_para_disenador_no_asignado(client, usuario_factory, proyecto_factory):
    d = usuario_factory(rol="disenador")
    p = proyecto_factory()
    client.force_login(d)
    assert client.get(f"/proyectos/{p.pk}/").status_code == 403


def test_asignar_y_quitar(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    d = usuario_factory(rol="disenador")
    p = proyecto_factory()
    client.force_login(admin)
    client.post(f"/proyectos/{p.pk}/asignar", {"usuario": d.pk, "rol_en_proyecto": "disenador"})
    from apps.los_proyectos.models import ProyectoAsignacion
    asig = ProyectoAsignacion.objects.get(proyecto=p, usuario=d)
    client.post(f"/proyectos/{p.pk}/asignar", {"accion": "quitar", "asignacion_id": asig.pk})
    assert not ProyectoAsignacion.objects.filter(pk=asig.pk).exists()
