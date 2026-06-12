"""El form de Rol usa checkboxes (no JSON crudo) y persiste el dict correcto."""

import pytest
from django.test import override_settings
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_form_rol_nuevo_renderiza_grilla_no_json(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get(reverse("directorio-rol-nuevo"))
    assert resp.status_code == 200
    html = resp.content.decode()
    # Grilla de checkboxes con valores modulo.accion; ya no hay textarea JSON.
    assert 'name="permisos"' in html
    assert 'value="cartera.ver"' in html
    assert 'name="permisos_json"' not in html


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_crear_rol_desde_checkboxes_persiste_dict(client, usuario_factory):
    from cuentas.models.rol import Rol
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(reverse("directorio-rol-nuevo"), {
        "nombre": "supervisor_x", "descripcion": "Prueba",
        "permisos": ["cartera.ver", "cartera.crear", "proyectos.ver"],
    })
    assert resp.status_code == 302
    rol = Rol.objects.get(nombre="supervisor_x")
    assert rol.permisos == {"cartera": ["ver", "crear"], "proyectos": ["ver"]}
