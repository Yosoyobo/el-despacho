"""S-LC-Feedback-V6 Bloque 2: página Tareas Kanban + form Nueva Tarea global."""

from datetime import date, timedelta

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture()
def entorno(usuario_factory, cliente_factory):
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.models import Proyecto
    admin = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="contador")
    cli = cliente_factory(creado_por=admin)
    p = Proyecto.objects.create(nombre="P1", cliente=cli, creado_por=admin)
    t_mia = Tarea.objects.create(proyecto=p, titulo="Mía", asignada_a=admin,
                                 creado_por=admin, estado="pendiente")
    t_otro = Tarea.objects.create(proyecto=p, titulo="De otro", asignada_a=otro,
                                  creado_por=admin, estado="en_curso")
    t_cerrada = Tarea.objects.create(proyecto=p, titulo="Cerrada", asignada_a=admin,
                                     creado_por=admin, estado="completada")
    return {"admin": admin, "otro": otro, "proyecto": p,
            "t_mia": t_mia, "t_otro": t_otro, "t_cerrada": t_cerrada}


def test_default_muestra_todo_el_despacho(client, entorno):
    """LC Fase 2: el default del tablero ya NO filtra a 'mis tareas' — muestra
    todas las tareas vigentes del despacho."""
    client.force_login(entorno["admin"])
    body = client.get("/tareas/").content.decode()
    assert "Mía" in body
    assert "De otro" in body              # ahora el default muestra todo el despacho
    assert "Cerrada" in body              # las cerradas siguen en la fila de abajo


def test_filtros_combinables(client, entorno):
    client.force_login(entorno["admin"])
    otro_pk = entorno["otro"].pk
    admin_pk = entorno["admin"].pk
    # Dos personas combinadas → ambas tareas visibles.
    body = client.get(f"/tareas/?f=1&persona={admin_pk}&persona={otro_pk}").content.decode()
    assert "Mía" in body and "De otro" in body
    # Persona + estado combinados.
    body = client.get(f"/tareas/?f=1&persona={otro_pk}&estado=en_curso").content.decode()
    assert "De otro" in body and "Mía" not in body


def test_sin_filtros_explicitos_muestra_todo(client, entorno):
    client.force_login(entorno["admin"])
    body = client.get("/tareas/?f=1").content.decode()
    assert "Mía" in body and "De otro" in body


def test_cerradas_en_fila_aparte(client, entorno):
    client.force_login(entorno["admin"])
    body = client.get("/tareas/?f=1").content.decode()
    assert "Cerradas" in body


def test_cambiar_estado_drag(client, entorno):
    client.force_login(entorno["admin"])
    t = entorno["t_mia"]
    resp = client.post(f"/tareas/{t.pk}/cambiar-estado", {"estado": "completada"})
    assert resp.status_code == 204
    t.refresh_from_db()
    assert t.estado == "completada"
    assert t.completada_en is not None
    # Volver a un estado no terminal limpia completada_en.
    client.post(f"/tareas/{t.pk}/cambiar-estado", {"estado": "en_curso"})
    t.refresh_from_db()
    assert t.completada_en is None


def test_cambiar_estado_invalido_403(client, entorno):
    client.force_login(entorno["admin"])
    t = entorno["t_mia"]
    resp = client.post(f"/tareas/{t.pk}/cambiar-estado", {"estado": "no_existe"})
    assert resp.status_code == 403


def test_form_global_crea_con_tipo_hora(client, entorno):
    client.force_login(entorno["admin"])
    resp = client.post("/tareas/nueva/", {
        "proyecto": entorno["proyecto"].pk,
        "titulo": "Junta con cliente",
        "descripcion": "",
        "tipo": "junta",
        "asignada_a": entorno["otro"].pk,
        "fecha_compromiso": (date.today() + timedelta(days=2)).isoformat(),
        "hora": "10:00",
    }, follow=True)
    assert resp.status_code == 200
    from apps.el_pizarron.models import Tarea
    t = Tarea.objects.get(titulo="Junta con cliente")
    assert t.tipo == "junta"
    assert t.estado == "pendiente"     # default sin campo estado en el form
    assert t.prioridad == "media"      # default sin campo prioridad visible
    assert t.proyecto_id == entorno["proyecto"].pk


def test_form_global_sin_proyecto_falla(client, entorno):
    client.force_login(entorno["admin"])
    resp = client.post("/tareas/nueva/", {
        "titulo": "Sin proyecto", "descripcion": "", "tipo": "tarea",
        "asignada_a": entorno["admin"].pk,
        "fecha_compromiso": date.today().isoformat(),
    })
    assert resp.status_code == 200  # re-render con error
    from apps.el_pizarron.models import Tarea
    assert not Tarea.objects.filter(titulo="Sin proyecto").exists()


def test_lista_sigue_viva(client, entorno):
    client.force_login(entorno["admin"])
    assert client.get("/tareas/lista/").status_code == 200
