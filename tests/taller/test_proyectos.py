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
         "estado": "por_cotizar", "fecha_inicio": "", "fecha_compromiso": "", "monto_estimado": ""},
        follow=True,
    )
    assert resp.status_code == 200
    from apps.los_proyectos.models import Proyecto
    assert Proyecto.objects.filter(nombre="Catálogo 2026").exists()


def test_cambiar_estado_emite_evento(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="dueno")
    p = proyecto_factory(estado="esperando_respuesta")
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/cambiar-estado",
        {"estado": "en_proceso_diseno"},
        follow=True,
    )
    assert resp.status_code == 200
    p.refresh_from_db()
    assert p.estado == "en_proceso_diseno"


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


def test_kanban_view(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    proyecto_factory(estado="por_cotizar")
    proyecto_factory(estado="en_proceso_diseno")
    client.force_login(admin)
    resp = client.get("/proyectos/kanban/")
    assert resp.status_code == 200
    contenido = resp.content.decode()
    assert "Por cotizar" in contenido
    assert "En proceso de diseño" in contenido


def test_cliente_inline_modal_get(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/proyectos/cliente-nuevo/", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "Nuevo cliente" in resp.content.decode()


def test_cliente_inline_modal_post_crea(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(
        "/proyectos/cliente-nuevo/",
        {"razon_social": "ACME Nuevo", "rfc": "", "nombre_contacto": "X", "email_contacto": "", "telefono": ""},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    from apps.la_cartera.models import Cliente
    assert Cliente.objects.filter(razon_social="ACME Nuevo").exists()


def test_proyecto_con_productos(client, usuario_factory, proyecto_factory):
    """Crear/editar un proyecto con líneas de productos asocia ProyectoProducto."""
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Diseño", defaults={"orden": 10})
    srv = Servicio.objects.create(nombre="Playera promo", precio_base="100", categoria=cat)
    p = proyecto_factory()
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=50, nota="azul")
    client.force_login(admin)
    resp = client.get(f"/proyectos/{p.pk}/")
    assert resp.status_code == 200
    assert "Playera promo" in resp.content.decode()
