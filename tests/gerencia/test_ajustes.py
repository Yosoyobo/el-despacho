"""Los Ajustes — UI de credenciales cifradas + sub-sección de tasas.

Solo super_admin tiene acceso (regla #3 del proyecto).
"""

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def test_dueno_no_accede(client, usuario_factory):
    client.force_login(usuario_factory(rol="dueno"))
    resp = client.get("/ajustes/")
    assert resp.status_code == 403


def test_super_admin_ve_panel(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/ajustes/")
    assert resp.status_code == 200
    # Slots conocidos deben aparecer en el HTML.
    body = resp.content.decode()
    assert "anthropic_api_key" in body
    assert "openai_api_key" in body


def test_guardar_credencial_cifra(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/guardar", {
        "clave": "anthropic_api_key",
        "valor": "sk-ant-test-secret-abc123",
    })
    assert resp.status_code == 302
    # En DB no está el valor en claro.
    row = Credencial.objects.get(clave="anthropic_api_key")
    assert "sk-ant-test-secret-abc123" not in row.valor_cifrado
    # Pero `obtener()` lo recupera.
    assert Credencial.obtener("anthropic_api_key") == "sk-ant-test-secret-abc123"


def test_guardar_vacio_elimina(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    Credencial.guardar("openai_api_key", "sk-openai-aaaa")
    client.force_login(usuario_factory(rol="super_admin"))
    client.post("/ajustes/guardar", {"clave": "openai_api_key", "valor": ""})
    assert not Credencial.objects.filter(clave="openai_api_key").exists()


def test_slot_desconocido_rechazado_sin_flag(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/guardar", {"clave": "slot_random", "valor": "x"}, follow=True)
    assert resp.status_code == 200
    assert not Credencial.objects.filter(clave="slot_random").exists()


def test_slot_desconocido_aceptado_con_flag(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    client.force_login(usuario_factory(rol="super_admin"))
    client.post("/ajustes/guardar", {
        "clave": "slot_random", "valor": "v", "permitir_custom": "on",
    })
    assert Credencial.objects.filter(clave="slot_random").exists()


def test_probar_descifra(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    Credencial.guardar("anthropic_api_key", "sk-real-xxxxxxxx")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/anthropic_api_key/probar", follow=True)
    assert resp.status_code == 200
    # El flash debe indicar éxito (longitud N chars).
    body = resp.content.decode()
    assert "descifrable" in body or "longitud" in body
