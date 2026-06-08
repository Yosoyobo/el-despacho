"""Wrapper Google Drive — OAuth sin clave (Opción B). httpx mockeado."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

# ── Fake httpx.Client que enruta por URL ──────────────────────────────────────


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)


def _fake_client(*, token_resp=None, drive_post=None, drive_get=None):
    """Parchea lib.google_drive.httpx.Client enrutando por URL."""
    from lib import google_drive as gd

    class _Client:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, data=None, headers=None, params=None, json=None):
            if url == gd.TOKEN_URL:
                return token_resp or _FakeResp(200, {"access_token": "at-123", "refresh_token": "rt-xyz"})
            return drive_post or _FakeResp(200, {"id": "carpeta-nueva", "name": gd.CARPETA_RAIZ_NOMBRE})

        def get(self, url, headers=None, params=None):
            return drive_get or _FakeResp(200, {"id": "carpeta-existente", "name": gd.CARPETA_RAIZ_NOMBRE})

    return patch("lib.google_drive.httpx.Client", _Client)


def _config_oauth():
    """Siembra el cliente OAuth compartido (id+secret) en La Bóveda."""
    from ajustes.models.credencial import Credencial
    Credencial.guardar("google_oauth_client_id", "cid.apps.googleusercontent.com")
    Credencial.guardar("google_oauth_client_secret", "secret-xyz")


# ── Configuración / estado ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_esta_configurado_falso_sin_refresh_token():
    from lib.google_drive import GoogleDriveWrapper
    _config_oauth()
    assert GoogleDriveWrapper().esta_configurado() is False


@pytest.mark.django_db
def test_esta_configurado_y_conectado():
    from ajustes.models.credencial import Credencial
    from lib.google_drive import GoogleDriveWrapper
    _config_oauth()
    Credencial.guardar("google_drive_oauth_refresh_token", "rt-xyz")
    w = GoogleDriveWrapper()
    assert w.esta_configurado() is True
    assert w.esta_conectado() is False  # falta carpeta
    Credencial.guardar("google_drive_carpeta_raiz_id", "carpeta-1")
    assert w.esta_conectado() is True


@pytest.mark.django_db
def test_slots_drive_ya_no_estan_en_catalogo():
    """Los slots de Drive se gestionan por el asistente, no en el panel."""
    from ajustes.models.credencial import SLOTS_CREDENCIAL
    claves = {c for c, _, _ in SLOTS_CREDENCIAL}
    assert "google_drive_oauth_refresh_token" not in claves
    assert "google_drive_service_account_json" not in claves


# ── Flujo de consentimiento ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_url_consentimiento_pide_offline_y_scope_drive_file():
    from lib.google_drive import construir_url_consentimiento
    _config_oauth()
    url = construir_url_consentimiento("https://x/callback", "estado123")
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "drive.file" in url
    assert "estado123" in url


@pytest.mark.django_db
def test_intercambiar_codigo_devuelve_refresh():
    from lib.google_drive import intercambiar_codigo_por_refresh_token
    _config_oauth()
    with _fake_client(token_resp=_FakeResp(200, {"refresh_token": "rt-nuevo"})):
        rt = intercambiar_codigo_por_refresh_token("code-abc", "https://x/callback")
    assert rt == "rt-nuevo"


@pytest.mark.django_db
def test_intercambiar_codigo_sin_refresh_falla():
    from lib.google_drive import NoConfiguradoError, intercambiar_codigo_por_refresh_token
    _config_oauth()
    with _fake_client(token_resp=_FakeResp(200, {"access_token": "at"})), \
         pytest.raises(NoConfiguradoError, match="refresh token"):  # sin refresh_token
        intercambiar_codigo_por_refresh_token("code", "https://x/callback")


# ── Carpeta raíz ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_crea_carpeta_raiz_si_no_existe():
    from ajustes.models.credencial import Credencial
    from lib.google_drive import GoogleDriveWrapper
    _config_oauth()
    Credencial.guardar("google_drive_oauth_refresh_token", "rt-xyz")
    w = GoogleDriveWrapper()
    with _fake_client(drive_post=_FakeResp(200, {"id": "nueva-123", "name": "El Despacho - Adjuntos"})):
        carpeta_id = w.obtener_o_crear_carpeta_raiz()
    assert carpeta_id == "nueva-123"
    assert Credencial.obtener("google_drive_carpeta_raiz_id") == "nueva-123"


@pytest.mark.django_db
def test_reusa_carpeta_raiz_existente():
    from ajustes.models.credencial import Credencial
    from lib.google_drive import GoogleDriveWrapper
    _config_oauth()
    Credencial.guardar("google_drive_oauth_refresh_token", "rt-xyz")
    Credencial.guardar("google_drive_carpeta_raiz_id", "vieja-999")
    w = GoogleDriveWrapper()
    with _fake_client(drive_get=_FakeResp(200, {"id": "vieja-999", "name": "x", "trashed": False})):
        carpeta_id = w.obtener_o_crear_carpeta_raiz()
    assert carpeta_id == "vieja-999"


# ── probar() ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_probar_no_conectado_sin_refresh():
    from lib.google_drive import GoogleDriveWrapper
    _config_oauth()
    res = GoogleDriveWrapper().probar()
    assert res["ok"] is False
    assert res["estado"] == "no_conectado"


@pytest.mark.django_db
def test_probar_ok():
    from ajustes.models.credencial import Credencial
    from lib.google_drive import GoogleDriveWrapper
    _config_oauth()
    Credencial.guardar("google_drive_oauth_refresh_token", "rt-xyz")
    w = GoogleDriveWrapper()
    with _fake_client(drive_post=_FakeResp(200, {"id": "c-1", "name": "El Despacho - Adjuntos"})):
        res = w.probar()
    assert res["ok"] is True
    assert res["estado"] == "ok"


# ── Adjuntos: subir / descargar ───────────────────────────────────────────────


class _FakeRespArchivo:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)


def _fake_client_archivo(*, upload_resp=None, media_resp=None, meta_resp=None):
    """Fake que enruta token/subida/descarga; el post de subida usa `content=`."""
    from lib import google_drive as gd

    class _Client:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, data=None, headers=None, params=None, json=None, content=None):
            if url == gd.TOKEN_URL:
                return _FakeRespArchivo(200, {"access_token": "at-123"})
            return upload_resp or _FakeRespArchivo(
                200, {"id": "file-1", "name": "foto.png", "mimeType": "image/png", "size": "4"}
            )

        def get(self, url, headers=None, params=None):
            if params and params.get("alt") == "media":
                return media_resp or _FakeRespArchivo(200, content=b"PNGDATA")
            return meta_resp or _FakeRespArchivo(200, {"name": "foto.png", "mimeType": "image/png"})

    return patch("lib.google_drive.httpx.Client", _Client)


@pytest.mark.django_db
def test_subir_fileobj_devuelve_metadata():
    import io

    from ajustes.models.credencial import Credencial
    from lib.google_drive import GoogleDriveWrapper
    _config_oauth()
    Credencial.guardar("google_drive_oauth_refresh_token", "rt-xyz")
    w = GoogleDriveWrapper()
    with _fake_client_archivo():
        res = w.subir_fileobj(io.BytesIO(b"data"), "foto.png", "carpeta-1", "image/png")
    assert res["id"] == "file-1"
    assert res["name"] == "foto.png"


@pytest.mark.django_db
def test_descargar_devuelve_contenido_mime_y_nombre():
    from ajustes.models.credencial import Credencial
    from lib.google_drive import GoogleDriveWrapper
    _config_oauth()
    Credencial.guardar("google_drive_oauth_refresh_token", "rt-xyz")
    w = GoogleDriveWrapper()
    with _fake_client_archivo():
        contenido, mime, nombre = w.descargar("file-1")
    assert contenido == b"PNGDATA"
    assert mime == "image/png"
    assert nombre == "foto.png"


def test_dependencias_google_importables():
    import googleapiclient.discovery  # noqa: F401
    from google.oauth2 import service_account  # noqa: F401


def test_doc_setup_drive_existe():
    from pathlib import Path
    doc = Path(__file__).resolve().parent.parent / "docs" / "SETUP_GOOGLE_DRIVE.md"
    assert doc.exists(), "docs/SETUP_GOOGLE_DRIVE.md no existe"
    contenido = doc.read_text()
    # Método sin clave (OAuth), no service account.
    assert "refresh token" in contenido.lower() or "token de actualización" in contenido.lower()


def test_form_recados_adjuntos_desenmascarado():
    """El botón 📎 dejó de estar disabled: ahora el form sube adjuntos de verdad."""
    from pathlib import Path
    form = Path(__file__).resolve().parent.parent / "el-taller" / "templates" / "recados" / "form.html"
    contenido = form.read_text()
    assert "📎" in contenido
    assert 'enctype="multipart/form-data"' in contenido
    assert 'name="adjuntos"' in contenido
    # Ya no debe quedar el botón muerto que apuntaba a la doc de setup.
    assert "cursor-not-allowed" not in contenido
