"""S-LC-Feedback-V6 Bloque 7C: campañas de correo masivo (Gerencia)."""

from unittest import mock

import pytest
from django.test import override_settings

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


class _OK:
    ok = True
    error = ""


class _Falla:
    ok = False
    error = "rebotó"


@pytest.fixture()
def entorno(usuario_factory, cliente_factory):
    admin = usuario_factory(rol="super_admin")
    from cuentas.models.permiso_usuario import PermisoUsuario
    PermisoUsuario.objects.get_or_create(usuario=admin, modulo="comunicacion",
                                         permiso="campanas", defaults={"activo": True})
    clientes = []
    for i, estado in enumerate(["activo", "activo", "prospecto"]):
        c = cliente_factory(creado_por=admin, razon_social=f"Cliente {i}")
        c.email_contacto = f"c{i}@x.mx"
        c.estado = estado
        c.save()
        clientes.append(c)
    return admin, clientes


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_gate_sin_permiso(client, usuario_factory):
    u = usuario_factory(rol="contador")
    client.force_login(u)
    assert client.get("/campanas/").status_code == 403


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_nueva_muestra_clientes_con_email(client, entorno):
    admin, clientes = entorno
    client.force_login(admin)
    body = client.get("/campanas/nueva/").content.decode()
    for c in clientes:
        assert c.razon_social in body


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_post_sin_confirmar_muestra_confirmacion(client, entorno):
    """Primera pasada → página de confirmación con el total, SIN enviar."""
    admin, clientes = entorno
    client.force_login(admin)
    with mock.patch("lib.cartero.enviar", return_value=_OK()) as m:
        body = client.post("/campanas/nueva/", {
            "plantilla": "generico", "asunto": "Hola", "mensaje": "Promo del mes",
            "clientes": [c.pk for c in clientes],
        }).content.decode()
        m.assert_not_called()
    assert "Vas a enviar este correo a 3 cliente" in body
    from apps.campanas.models import CampanaCorreo
    assert CampanaCorreo.objects.count() == 0


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_envio_confirmado_best_effort(client, entorno):
    """Confirmado → envía a todos; un fallo no aborta el lote; audita."""
    admin, clientes = entorno
    client.force_login(admin)
    resultados = [_OK(), _Falla(), _OK()]
    with mock.patch("lib.cartero.enviar", side_effect=resultados):
        resp = client.post("/campanas/nueva/", {
            "plantilla": "generico", "asunto": "Hola", "mensaje": "Promo",
            "clientes": [c.pk for c in clientes], "confirmado": "1",
        }, follow=True)
    assert resp.status_code == 200
    from apps.campanas.models import CampanaCorreo
    campana = CampanaCorreo.objects.get()
    assert campana.total_destinatarios == 3
    assert campana.enviados == 2
    assert campana.fallidos == 1
    assert campana.envios.filter(estado="fallido").count() == 1


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_generico_sin_mensaje_no_envia(client, entorno):
    admin, clientes = entorno
    client.force_login(admin)
    with mock.patch("lib.cartero.enviar", return_value=_OK()) as m:
        client.post("/campanas/nueva/", {
            "plantilla": "generico", "asunto": "", "mensaje": "",
            "clientes": [clientes[0].pk], "confirmado": "1",
        })
        m.assert_not_called()
