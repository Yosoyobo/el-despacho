"""Tests de El Pizarrón: tareas, comentarios polimórficos, visibilidad por rol."""

import pytest
from django.db import IntegrityError

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_admin_crea_tarea(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/tareas/nueva",
        {"titulo": "Diseñar portada", "descripcion": "",
         "estado": "pendiente", "prioridad": "alta",
         "asignada_a": admin.pk, "fecha_compromiso": "2030-01-15"},
        follow=True,
    )
    assert resp.status_code == 200
    from apps.el_pizarron.models import Tarea
    t = Tarea.objects.get(titulo="Diseñar portada", proyecto=p)
    assert t.asignada_a_id == admin.pk
    assert t.fecha_compromiso.isoformat() == "2030-01-15"


def test_tarea_sin_asignado_o_fecha_falla(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/tareas/nueva",
        {"titulo": "X", "descripcion": "", "estado": "pendiente", "prioridad": "media",
         "asignada_a": "", "fecha_compromiso": ""},
    )
    assert resp.status_code == 200
    from apps.el_pizarron.models import Tarea
    assert not Tarea.objects.filter(titulo="X").exists()


def test_disenador_asignado_crea_y_completa_tarea(client, usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.models import ProyectoAsignacion

    d = usuario_factory(rol="disenador")
    p = proyecto_factory()
    ProyectoAsignacion.objects.create(proyecto=p, usuario=d, rol_en_proyecto="disenador")
    client.force_login(d)
    client.post(
        f"/proyectos/{p.pk}/tareas/nueva",
        {"titulo": "Render final", "descripcion": "",
         "estado": "pendiente", "prioridad": "media",
         "asignada_a": d.pk, "fecha_compromiso": "2030-02-01"},
    )
    t = Tarea.objects.get(titulo="Render final")
    client.post(f"/tareas/{t.pk}/completar")
    t.refresh_from_db()
    assert t.estado == "completada"
    assert t.completada_en is not None


def test_disenador_no_asignado_403(client, usuario_factory, proyecto_factory):
    d = usuario_factory(rol="disenador")
    p = proyecto_factory()
    client.force_login(d)
    assert client.get(f"/proyectos/{p.pk}/tareas/nueva").status_code == 403


def test_comentario_polimorfico_check_constraint(usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Comentario

    autor = usuario_factory()
    proyecto_factory()  # asegura que hay al menos un proyecto en DB (no se referencia)
    # Ambos NULL → debe fallar el CHECK.
    with pytest.raises(IntegrityError):
        Comentario.objects.create(autor=autor, cuerpo="huérfano", es_interno=False)


def test_comentario_solo_a_tarea_o_proyecto(usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Comentario, Tarea

    autor = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="X", creado_por=autor)
    c1 = Comentario.objects.create(autor=autor, tarea=t, cuerpo="sobre tarea")
    c2 = Comentario.objects.create(autor=autor, proyecto=p, cuerpo="sobre proyecto")
    assert c1.destino_proyecto == p
    assert c2.destino_proyecto == p


def test_comentario_ambos_llenos_falla(usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Comentario, Tarea

    autor = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="X", creado_por=autor)
    with pytest.raises(IntegrityError):
        Comentario.objects.create(autor=autor, tarea=t, proyecto=p, cuerpo="ambos")


def test_disenador_no_ve_comentario_interno_ajeno(client, usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Comentario, Tarea
    from apps.los_proyectos.models import ProyectoAsignacion

    admin = usuario_factory(rol="super_admin")
    d = usuario_factory(rol="disenador")
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="T", creado_por=admin)
    ProyectoAsignacion.objects.create(proyecto=p, usuario=d, rol_en_proyecto="disenador")
    Comentario.objects.create(autor=admin, tarea=t, cuerpo="SECRETO", es_interno=True)
    Comentario.objects.create(autor=admin, tarea=t, cuerpo="PUBLICO", es_interno=False)
    client.force_login(d)
    resp = client.get(f"/tareas/{t.pk}/")
    assert resp.status_code == 200
    contenido = resp.content.decode()
    assert "PUBLICO" in contenido
    assert "SECRETO" not in contenido


def test_comentario_de_disenador_no_puede_ser_interno(client, usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Comentario, Tarea
    from apps.los_proyectos.models import ProyectoAsignacion

    admin = usuario_factory(rol="super_admin")
    d = usuario_factory(rol="disenador")
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="T", creado_por=admin)
    ProyectoAsignacion.objects.create(proyecto=p, usuario=d, rol_en_proyecto="disenador")
    client.force_login(d)
    client.post(f"/tareas/{t.pk}/comentar", {"cuerpo": "hola", "es_interno": "on"})
    c = Comentario.objects.get(tarea=t, autor=d)
    assert c.es_interno is False  # diseñador no puede marcar interno


def test_textarea_comentario_tiene_referencias(client, usuario_factory, proyecto_factory):
    """Regresión S-Chalanes-UX #1: el textarea de comentarios debe traer
    data-referencias para que funcione el autocompletar @/#/$."""
    from apps.el_pizarron.models import Tarea
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    t = Tarea.objects.create(proyecto=p, titulo="X", asignada_a=admin,
                             estado="pendiente", prioridad="media")
    client.force_login(admin)
    resp = client.get(f"/tareas/{t.pk}/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="cuerpo"' in body
    assert "data-referencias" in body


def test_detalle_proyecto_tiene_form_comentarios_con_referencias(
    client, usuario_factory, proyecto_factory):
    """S-Chalanes-UX #1: el detalle del proyecto ahora muestra el form de
    comentarios con data-referencias (antes la URL existía pero no la UI)."""
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    client.force_login(admin)
    resp = client.get(f"/proyectos/{p.pk}/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "pizarron-comentar-proyecto" in body or f"/proyectos/{p.pk}/comentar" in body
    assert 'name="cuerpo"' in body
    assert "data-referencias" in body


def test_comentar_proyecto_persiste_y_se_ve(client, usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Comentario
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    client.force_login(admin)
    resp = client.post(f"/proyectos/{p.pk}/comentar",
                       {"cuerpo": "Nota del proyecto"}, follow=True)
    assert resp.status_code == 200
    assert Comentario.objects.filter(proyecto=p, cuerpo="Nota del proyecto").exists()
    assert "Nota del proyecto" in resp.content.decode()


def test_badge_tareas_involucrado_vs_otras(proyecto_factory, usuario_factory):
    """LC 2026-06-30 (2ª pasada): el globo azul cuenta SOLO las tareas asignadas a
    quien mira; el gris, las demás pendientes del despacho."""
    from apps.el_pizarron.context_processors import mandados_badge
    from apps.el_pizarron.models import Tarea
    from django.test import RequestFactory
    admin = usuario_factory(rol="super_admin")
    dis = usuario_factory(rol="disenador")
    p = proyecto_factory(creado_por=admin)
    Tarea.objects.create(proyecto=p, titulo="Mía", creado_por=admin, asignada_a=dis)
    Tarea.objects.create(proyecto=p, titulo="De otro", creado_por=admin, asignada_a=admin)
    req = RequestFactory().get("/")
    req.user = dis
    ctx = mandados_badge(req)
    assert ctx["tareas_involucrado_count"] == 1   # azul = la asignada al diseñador
    assert ctx["tareas_otras_count"] == 1          # gris = la otra (no es suya)


def test_badge_tareas_no_involucrado_solo_gris(proyecto_factory, usuario_factory):
    """Si no tiene ninguna asignada, el azul queda en 0 y solo se ve el gris con
    el total."""
    from apps.el_pizarron.context_processors import mandados_badge
    from apps.el_pizarron.models import Tarea
    from django.test import RequestFactory
    admin = usuario_factory(rol="super_admin")
    ajeno = usuario_factory(rol="disenador")
    p = proyecto_factory(creado_por=admin)
    Tarea.objects.create(proyecto=p, titulo="A", creado_por=admin, asignada_a=admin)
    Tarea.objects.create(proyecto=p, titulo="B", creado_por=admin, asignada_a=admin)
    req = RequestFactory().get("/")
    req.user = ajeno
    ctx = mandados_badge(req)
    assert ctx["tareas_involucrado_count"] == 0
    assert ctx["tareas_otras_count"] == 2


def test_badge_estar_en_el_equipo_no_infla_el_azul(proyecto_factory, usuario_factory):
    """Regresión del caso Oscar: estar en el EQUIPO de un proyecto (asignación)
    NO cuenta como tarea propia. Sin tareas asignadas a él ni mandados suyos, el
    azul y el rojo quedan en 0 — solo ve el gris con el total del despacho."""
    from apps.el_pizarron.context_processors import mandados_badge
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.models.asignacion import ProyectoAsignacion
    from django.test import RequestFactory
    jefe = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="disenador")
    p = proyecto_factory(creado_por=jefe)
    # `jefe` está en el equipo del proyecto, pero la tarea es de `otro`.
    ProyectoAsignacion.objects.create(proyecto=p, usuario=jefe, rol_en_proyecto="lider")
    Tarea.objects.create(proyecto=p, titulo="De otro", creado_por=jefe, asignada_a=otro)
    req = RequestFactory().get("/")
    req.user = jefe
    ctx = mandados_badge(req)
    assert ctx["tareas_involucrado_count"] == 0   # azul: no tiene tareas propias
    assert ctx["tareas_otras_count"] == 1          # gris: la del despacho
    assert ctx["mandados_pendientes_count"] == 0   # rojo: no tiene mandados suyos
