"""S-LC-Feedback-V6 Bloque 1: CRUD de Estados de tarea en La Gerencia."""

import pytest
from django.test import override_settings

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_lista_solo_super_admin(client, usuario_factory):
    u = usuario_factory(rol="contador")
    client.force_login(u)
    assert client.get("/catalogos/estados-tarea/").status_code == 403
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/catalogos/estados-tarea/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Pendiente" in body and "Completada" in body


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_crear_estado_nuevo(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-tarea/nuevo/", {
        "slug": "en_revision", "label": "En revisión", "color": "#7a5af8",
        "orden": "25", "activo": "on",
    }, follow=True)
    assert resp.status_code == 200
    from apps.el_pizarron.models import EstadoTarea
    e = EstadoTarea.objects.get(slug="en_revision")
    assert e.sistema is False
    assert e.color == "#7a5af8"


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_no_borra_estado_sistema(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    client.post("/catalogos/estados-tarea/pendiente/borrar/", follow=True)
    from apps.el_pizarron.models import EstadoTarea
    assert EstadoTarea.objects.filter(slug="pendiente").exists()


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_toggle_activo(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    client.post("/catalogos/estados-tarea/en_curso/toggle/", follow=True)
    from apps.el_pizarron.models import EstadoTarea
    assert EstadoTarea.objects.get(slug="en_curso").activo is False


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_editar_label_se_refleja_en_mapa(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    client.post("/catalogos/estados-tarea/pendiente/editar/", {
        "label": "Por hacer", "color": "#0ba5ec", "orden": "10", "activo": "on",
    }, follow=True)
    from apps.el_pizarron.models import EstadoTarea
    assert EstadoTarea.objects.get(slug="pendiente").label == "Por hacer"
    # El cache se invalida vía signal → el filtro lee el label nuevo.
    from apps.el_pizarron.templatetags.tareas_extras import estado_label_tarea
    assert estado_label_tarea("pendiente") == "Por hacer"
