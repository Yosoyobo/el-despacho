"""S-Recados-V2 (C5b): feed ActividadProyecto + hooks."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_registrar_y_feed_admin_ve_todo(usuario_factory, proyecto_factory):
    from apps.los_proyectos import servicios_actividad
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(creado_por=admin)
    servicios_actividad.registrar(proyecto=p, tipo="estado_cambiado",
                                  descripcion="x", actor=admin, url=f"/proyectos/{p.pk}/")
    feed = servicios_actividad.feed_para(admin)
    assert len(feed) == 1
    assert feed[0].tipo == "estado_cambiado"


def test_feed_filtra_por_asignacion(usuario_factory, proyecto_factory):
    from apps.los_proyectos import servicios_actividad
    from apps.los_proyectos.models import ProyectoAsignacion
    admin = usuario_factory(rol="super_admin")
    lider = usuario_factory(rol="disenador")
    ajeno = usuario_factory(rol="disenador")
    p = proyecto_factory(creado_por=admin)
    ProyectoAsignacion.objects.create(proyecto=p, usuario=lider, rol_en_proyecto="lider")
    servicios_actividad.registrar(proyecto=p, tipo="comentario", descripcion="y", actor=admin)
    assert len(servicios_actividad.feed_para(lider)) == 1
    assert len(servicios_actividad.feed_para(ajeno)) == 0


def test_cambiar_estado_genera_actividad(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ActividadProyecto
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(creado_por=admin)
    client.force_login(admin)
    # estados base existen vía seed; movemos a uno distinto del actual.
    from apps.los_proyectos.models import EstadoProyecto
    destino = EstadoProyecto.objects.filter(activo=True).exclude(slug=p.estado).first()
    client.post(f"/proyectos/{p.pk}/cambiar-estado", data={"estado": destino.slug})
    assert ActividadProyecto.objects.filter(proyecto=p, tipo="estado_cambiado").exists()
