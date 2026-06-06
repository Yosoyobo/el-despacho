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


# ── Asistente guiado de Google Drive (OAuth sin clave) ────────────────────────

def _config_oauth():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_oauth_client_id", "cid.apps.googleusercontent.com")
    Credencial.guardar("google_oauth_client_secret", "secret-xyz")


def test_drive_guia_solo_super_admin(client, usuario_factory):
    client.force_login(usuario_factory(rol="dueno"))
    assert client.get("/ajustes/google-drive/").status_code == 403


def test_drive_guia_renderiza_y_muestra_redirect_uri(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/ajustes/google-drive/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Conectar Google Drive" in body
    # La URI de callback debe mostrarse para registrarla en Google.
    assert "/ajustes/google-drive/oauth/callback" in body


def test_drive_guardar_cliente_desde_json(client, usuario_factory):
    """Pegar el JSON del cliente extrae id/secret a slots dedicados de Drive."""
    import json

    from ajustes.models.credencial import Credencial
    client.force_login(usuario_factory(rol="super_admin"))
    blob = json.dumps({"web": {
        "client_id": "525803625406-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-secreto",
        "project_id": "el-despacho-learning-center",
        "redirect_uris": ["https://testserver/ajustes/google-drive/oauth/callback"],
    }})
    resp = client.post("/ajustes/google-drive/cliente", {"cliente_json": blob}, follow=True)
    assert resp.status_code == 200
    assert Credencial.obtener("google_drive_oauth_client_id") == "525803625406-abc.apps.googleusercontent.com"
    assert Credencial.obtener("google_drive_oauth_client_secret") == "GOCSPX-secreto"
    # El callback estaba en redirect_uris → mensaje de éxito (no warning).
    assert b"ya est\xc3\xa1 registrada" in resp.content


def test_drive_guardar_cliente_json_invalido(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/google-drive/cliente", {"cliente_json": "no es json"}, follow=True)
    assert resp.status_code == 200
    assert not Credencial.esta_configurado("google_drive_oauth_client_id")


def test_drive_conectar_usa_cliente_dedicado(client, usuario_factory):
    """Con cliente dedicado de Drive (sin el de SSO), conectar funciona igual."""
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_drive_oauth_client_id", "drive-cid.apps.googleusercontent.com")
    Credencial.guardar("google_drive_oauth_client_secret", "drive-secret")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/google-drive/conectar")
    assert resp.status_code == 302
    assert "drive-cid.apps.googleusercontent.com" in resp.url


def test_drive_conectar_redirige_a_google(client, usuario_factory):
    _config_oauth()
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/google-drive/conectar")
    assert resp.status_code == 302
    assert resp.url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "access_type=offline" in resp.url


def test_drive_conectar_sin_oauth_avisa(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/google-drive/conectar", follow=True)
    # Sin cliente OAuth, no redirige a Google: vuelve al asistente con error.
    assert resp.status_code == 200
    assert b"cliente OAuth" in resp.content


def test_drive_callback_guarda_refresh_y_crea_carpeta(client, usuario_factory, monkeypatch):
    import lib.google_drive as gd
    from ajustes.models.credencial import Credencial
    _config_oauth()
    monkeypatch.setattr(gd, "intercambiar_codigo_por_refresh_token", lambda code, uri: "rt-nuevo")
    monkeypatch.setattr(gd.drive, "obtener_o_crear_carpeta_raiz", lambda: "carpeta-1")

    client.force_login(usuario_factory(rol="super_admin"))
    # Sembramos el state en la sesión como lo haría /conectar.
    s = client.session
    s["drive_oauth_state"] = "estado-ok"
    s.save()
    resp = client.get("/ajustes/google-drive/oauth/callback?code=abc&state=estado-ok")
    assert resp.status_code == 302
    assert Credencial.obtener("google_drive_oauth_refresh_token") == "rt-nuevo"


def test_drive_callback_rechaza_state_invalido(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    _config_oauth()
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/ajustes/google-drive/oauth/callback?code=abc&state=intruso", follow=True)
    assert resp.status_code == 200
    assert not Credencial.esta_configurado("google_drive_oauth_refresh_token")


def test_drive_desconectar_borra_credenciales(client, usuario_factory):
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_drive_oauth_refresh_token", "rt-xyz")
    Credencial.guardar("google_drive_carpeta_raiz_id", "carpeta-1")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/google-drive/desconectar")
    assert resp.status_code == 302
    assert not Credencial.esta_configurado("google_drive_oauth_refresh_token")
    assert not Credencial.esta_configurado("google_drive_carpeta_raiz_id")


def test_drive_probar_guarda_resultado(client, usuario_factory, monkeypatch):
    import lib.google_drive as gd
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_drive_oauth_refresh_token", "rt-xyz")
    monkeypatch.setattr(gd.drive, "probar", lambda: {
        "ok": True, "estado": "ok", "mensaje": "¡Listo! Conectado.",
    })
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/ajustes/google-drive/probar", follow=True)
    assert resp.status_code == 200
    fila = Credencial.objects.get(clave="google_drive_oauth_refresh_token")
    assert fila.ultimo_test_ok is True
    assert "Listo" in fila.ultimo_test_mensaje


def test_drive_guia_renderiza_semaforo_rojo(client, usuario_factory):
    """La rama 🔴 (último test falló) se renderiza sin TemplateSyntaxError."""
    from django.utils import timezone

    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_drive_oauth_refresh_token", "rt-xyz")
    fila = Credencial.objects.get(clave="google_drive_oauth_refresh_token")
    fila.ultimo_test_en = timezone.now()
    fila.ultimo_test_ok = False
    fila.ultimo_test_mensaje = "Reconecta desde el asistente"
    fila.save()

    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/ajustes/google-drive/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Aún falta algo" in body
    assert "Reconecta desde el asistente" in body
