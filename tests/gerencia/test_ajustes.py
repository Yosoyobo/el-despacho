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


# ── Asistente guiado de Google Drive ──────────────────────────────────────────

def test_drive_guia_solo_super_admin(client, usuario_factory):
    client.force_login(usuario_factory(rol="dueno"))
    assert client.get("/ajustes/google-drive/").status_code == 403


def test_drive_guia_renderiza(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/ajustes/google-drive/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Conectar Google Drive" in body
    assert "Probar conexión" in body


def test_drive_guardar_persiste_ambos_y_extrae_id_de_url(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/google-drive/guardar", {
        "service_account_json": '{"type":"service_account","client_email":"x@y.iam.gserviceaccount.com"}',
        "carpeta_raiz_id": "https://drive.google.com/drive/folders/1A2b3C4d5E?usp=sharing",
    })
    assert resp.status_code == 302
    assert Credencial.esta_configurado("google_drive_service_account_json")
    # El ID se extrae de la URL completa.
    assert Credencial.obtener("google_drive_carpeta_raiz_id") == "1A2b3C4d5E"


def test_drive_guardar_vacio_no_borra(client, usuario_factory):
    """Guardar con el JSON en blanco no debe borrar el JSON ya configurado."""
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_drive_service_account_json", '{"type":"service_account"}')
    client.force_login(usuario_factory(rol="super_admin"))
    client.post("/ajustes/google-drive/guardar", {
        "service_account_json": "",
        "carpeta_raiz_id": "1NUEVO",
    })
    # El JSON sobrevive; la carpeta se actualiza.
    assert Credencial.esta_configurado("google_drive_service_account_json")
    assert Credencial.obtener("google_drive_carpeta_raiz_id") == "1NUEVO"


def test_drive_probar_guarda_resultado(client, usuario_factory, monkeypatch):
    import lib.google_drive as gd
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_drive_carpeta_raiz_id", "1ABC")
    monkeypatch.setattr(gd.drive, "probar", lambda: {
        "ok": True, "estado": "ok", "mensaje": "¡Listo! Conectado.",
    })
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/google-drive/probar", follow=True)
    assert resp.status_code == 200
    fila = Credencial.objects.get(clave="google_drive_carpeta_raiz_id")
    assert fila.ultimo_test_ok is True
    assert "Listo" in fila.ultimo_test_mensaje


def test_drive_guia_renderiza_semaforo_rojo(client, usuario_factory):
    """La rama 🔴 (último test falló) se renderiza sin TemplateSyntaxError."""
    from django.utils import timezone

    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_drive_carpeta_raiz_id", "1ABC")
    fila = Credencial.objects.get(clave="google_drive_carpeta_raiz_id")
    fila.ultimo_test_en = timezone.now()
    fila.ultimo_test_ok = False
    fila.ultimo_test_mensaje = "comparte la carpeta"
    fila.save()

    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/ajustes/google-drive/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Aún falta algo" in body
    assert "comparte la carpeta" in body
