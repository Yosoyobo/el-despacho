"""Enlace público FIRMADO y temporal para imágenes dentro de los PDF.

Por qué existe este endpoint sin login: los PDF se generan vía Google Docs y
Google baja las imágenes del HTML de forma anónima, sin nuestra sesión ni
nuestra credencial de Drive (ver `lib.imagen_publica`). Estos tests blindan
los tres candados que lo sustituyen: firma + expiración, el `file_id` tiene
que ser de un producto real, y sólo se sirven `image/*`.
"""

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]



@pytest.fixture(autouse=True)
def _cache_limpia():
    """LC 2026-08-12: el proxy ya GUARDA en caché lo que baja de Drive (antes
    la leía pero nunca escribía). Sin limpiar entre pruebas, la imagen buena de
    un test sobrevive al Drive roto del siguiente."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
PNG = b"\x89PNG\r\n\x1a\n-bytes-de-prueba"


@pytest.fixture
def categoria(db):
    from apps.el_catalogo.models import CategoriaServicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Diseño", defaults={"orden": 10})
    return cat


@pytest.fixture
def producto_con_imagen(db, categoria):
    from apps.el_catalogo.models import Servicio
    return Servicio.objects.create(
        nombre="Gorras", precio_base="145.00", categoria=categoria,
        imagen_file_id="drive-abc123",
    )


def _mock_drive(monkeypatch, contenido=PNG, mime="image/png", falla=False):
    """Sustituye `drive.descargar` — los tests nunca pegan a Google."""
    from lib import google_drive

    def descargar(file_id):
        if falla:
            raise RuntimeError("Drive caído")
        return (contenido, mime, "gorras.png")

    monkeypatch.setattr(google_drive.drive, "descargar", descargar)


class TestFirma:

    def test_round_trip(self):
        from lib.imagen_publica import firmar, verificar
        assert verificar(firmar("drive-abc123")) == "drive-abc123"

    def test_token_alterado_no_verifica(self):
        from lib.imagen_publica import firmar, verificar
        token = firmar("drive-abc123")
        assert verificar(token[:-3] + "xyz") is None

    def test_token_basura_no_verifica(self):
        from lib.imagen_publica import verificar
        assert verificar("no-es-un-token") is None
        assert verificar("") is None

    def test_token_expirado_no_verifica(self):
        """Con ttl=0 el sello de tiempo ya quedó fuera de ventana."""
        import time

        from lib.imagen_publica import firmar, verificar
        token = firmar("drive-abc123")
        time.sleep(1.1)
        assert verificar(token, ttl=1) is None

    def test_url_absoluta_usa_taller_url_y_es_verificable(self, settings):
        from lib.imagen_publica import url_absoluta, verificar
        settings.TALLER_URL = "https://taller.learningcenter.mx/"
        url = url_absoluta("drive-abc123")
        assert url.startswith("https://taller.learningcenter.mx/catalogo/img/")
        # El token de la URL debe poder verificarse de vuelta.
        assert verificar(url.rsplit("/", 1)[-1]) == "drive-abc123"

    def test_url_absoluta_sin_file_id_es_vacia(self):
        from lib.imagen_publica import url_absoluta
        assert url_absoluta("") == ""


class TestEndpoint:

    def test_token_valido_sirve_la_imagen_sin_login(
        self, client, producto_con_imagen, monkeypatch
    ):
        """El caso que importa: Google llega ANÓNIMO y tiene que recibir bytes."""
        from lib.imagen_publica import firmar
        _mock_drive(monkeypatch)
        resp = client.get(f"/catalogo/img/{firmar('drive-abc123')}")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "image/png"
        assert resp.content == PNG

    def test_token_invalido_es_404(self, client, producto_con_imagen, monkeypatch):
        _mock_drive(monkeypatch)
        resp = client.get("/catalogo/img/token-falso")
        assert resp.status_code == 404

    def test_file_id_que_no_es_de_ningun_producto_es_404(self, client, monkeypatch):
        """Candado 2: un token bien firmado NO sirve para leer Drive a placer."""
        from lib.imagen_publica import firmar
        _mock_drive(monkeypatch)
        resp = client.get(f"/catalogo/img/{firmar('drive-de-otra-cosa')}")
        assert resp.status_code == 404

    def test_archivo_que_no_es_imagen_es_404(
        self, client, producto_con_imagen, monkeypatch
    ):
        """Candado 3: si el archivo dejó de ser imagen, no se sirve."""
        from lib.imagen_publica import firmar
        _mock_drive(monkeypatch, mime="application/pdf")
        resp = client.get(f"/catalogo/img/{firmar('drive-abc123')}")
        assert resp.status_code == 404

    def test_drive_caido_es_404_no_500(
        self, client, producto_con_imagen, monkeypatch
    ):
        from lib.imagen_publica import firmar
        _mock_drive(monkeypatch, falla=True)
        resp = client.get(f"/catalogo/img/{firmar('drive-abc123')}")
        assert resp.status_code == 404

    def test_post_no_permitido(self, client, producto_con_imagen):
        from lib.imagen_publica import firmar
        resp = client.post(f"/catalogo/img/{firmar('drive-abc123')}")
        assert resp.status_code == 405
