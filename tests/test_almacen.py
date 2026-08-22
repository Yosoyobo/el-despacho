"""El Almacén (S-Medios-V1): los medios en disco, sin Drive en el camino de lectura.

Cubre lo que el sprint promete: dedupe por contenido, derivados generados una
sola vez, EXIF enderezado, metadatos exactos para medir la foto en el documento,
la misma firma que `drive.descargar` y la importación perezosa que permite
desplegar antes de terminar el respaldo masivo.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from lib import almacen


@pytest.fixture(autouse=True)
def _almacen_temporal(settings, tmp_path):
    settings.MEDIOS_DIR = str(tmp_path / "medios")
    almacen.olvidar_meta()
    yield
    almacen.olvidar_meta()


def _jpeg(ancho: int = 1600, alto: int = 1200, color: str = "red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (ancho, alto), color).save(buf, format="JPEG")
    return buf.getvalue()


def _png_con_alfa(lado: int = 300) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (lado, lado), (255, 0, 0, 128)).save(buf, format="PNG")
    return buf.getvalue()


# ── Ingesta y layout ─────────────────────────────────────────────────────────

def test_guarda_original_y_meta_en_el_layout_esperado():
    datos = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="foto.jpg")
    clave = datos["id"]

    assert clave == almacen.clave_de_contenido(_jpeg())
    assert almacen.existe(clave)
    # orig/<2>/<2>/<huella-de-64>/archivo — el nombre del usuario nunca toca el disco
    orig = almacen._dir_orig(clave) / "archivo"
    assert orig.is_file()
    partes = orig.relative_to(almacen.raiz()).parts
    assert partes[0] == "orig" and len(partes[1]) == 2 and len(partes[2]) == 2
    assert len(partes[3]) == 64 and partes[4] == "archivo"

    guardado = almacen.meta(clave)
    assert guardado["mime"] == "image/jpeg"
    assert guardado["nombre"] == "foto.jpg"
    assert guardado["bytes"] == len(_jpeg())


def test_misma_foto_dos_veces_es_un_solo_archivo():
    """La misma imagen en cinco productos no debe ocupar cinco copias."""
    a = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="a.jpg")
    b = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="b.jpg")

    assert a["id"] == b["id"]
    assert b.get("duplicado") is True
    originales = list((almacen.raiz() / "orig").rglob("archivo"))
    assert len(originales) == 1


def test_clave_explicita_conserva_el_id_de_drive():
    """La importación guarda bajo el id que ya está en la base: cero migraciones."""
    datos = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="x.jpg",
                                  clave="1AbC-drive-id_99")

    assert datos["id"] == "1AbC-drive-id_99"
    assert almacen.existe("1AbC-drive-id_99")
    # El sha256 del contenido se conserva aparte, para poder deduplicar después.
    assert almacen.meta("1AbC-drive-id_99")["sha256"] == almacen.clave_de_contenido(_jpeg())


def test_el_nombre_del_usuario_no_puede_escapar_del_almacen():
    datos = almacen.guardar_bytes(_jpeg(), mime="image/jpeg",
                                  nombre="../../../etc/passwd")
    clave = datos["id"]

    assert (almacen._dir_orig(clave) / "archivo").is_file()
    assert almacen.meta(clave)["nombre"] == "../../../etc/passwd"  # sólo dato
    assert not (almacen.raiz().parent / "etc").exists()


# ── Derivados ────────────────────────────────────────────────────────────────

def test_derivados_se_generan_al_ingresar_y_respetan_el_lado():
    clave = almacen.guardar_bytes(_jpeg(1600, 1200), mime="image/jpeg",
                                  nombre="f.jpg")["id"]
    variantes = almacen.meta(clave)["variantes"]

    assert set(variantes) == set(almacen.VARIANTES)
    for nombre_variante, lado in almacen.VARIANTES.items():
        ruta = almacen.ruta_variante(clave, nombre_variante)
        assert ruta.is_file() and ruta.name == variantes[nombre_variante]
        with Image.open(ruta) as img:
            assert max(img.size) <= lado
        # Los derivados viven en `pub/`, la única carpeta que alcanza El Portero.
        assert ruta.relative_to(almacen.raiz()).parts[0] == "pub"


def test_derivado_con_transparencia_sale_png():
    clave = almacen.guardar_bytes(_png_con_alfa(), mime="image/png",
                                  nombre="logo.png")["id"]

    assert almacen.meta(clave)["variantes"]["w400"] == "w400.png"
    with Image.open(almacen.ruta_variante(clave, "w400")) as img:
        assert img.mode == "RGBA"


def test_exif_endereza_la_foto_acostada():
    """Antes de este sprint las fotos de iPhone salían de lado: nadie aplicaba
    la orientación EXIF."""
    img = Image.new("RGB", (400, 200), "blue")
    exif = img.getexif()
    exif[274] = 6  # Orientation: rotar 270°
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)

    clave = almacen.guardar_bytes(buf.getvalue(), mime="image/jpeg",
                                  nombre="acostada.jpg")["id"]
    guardado = almacen.meta(clave)

    assert (guardado["ancho"], guardado["alto"]) == (200, 400)
    with Image.open(almacen.ruta_variante(clave, "w400")) as der:
        assert der.size[1] > der.size[0]


def test_proporcion_es_exacta_y_sin_abrir_la_imagen():
    """La medida de la foto en la hoja sale del meta, no de volver a decodificar
    (antes, si no estaba en caché, el estimador la suponía cuadrada)."""
    clave = almacen.guardar_bytes(_jpeg(1000, 500), mime="image/jpeg",
                                  nombre="banner.jpg")["id"]

    assert almacen.proporcion(clave) == pytest.approx(0.5)
    assert almacen.proporcion("no-existe") == 0.0


def test_un_pdf_no_tiene_derivados():
    clave = almacen.guardar_bytes(b"%PDF-1.7 no soy imagen",
                                  mime="application/pdf", nombre="cfdi.pdf")["id"]

    assert almacen.meta(clave)["variantes"] == {}
    assert almacen.ruta_variante(clave, "w400") is None


def test_imagen_corrupta_no_tumba_la_subida():
    clave = almacen.guardar_bytes(b"esto dice ser jpeg pero no lo es",
                                  mime="image/jpeg", nombre="roto.jpg")["id"]

    assert almacen.existe(clave)          # el original se conserva
    assert almacen.meta(clave)["variantes"] == {}


def test_derivar_por_huella_regenera_lo_borrado():
    """Si `pub/` se borra a mano o un restore sólo trajo los originales, El
    Portero cae a Django y el derivado se rehace sin la llave."""
    clave = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="f.jpg")["id"]
    ruta = almacen.ruta_variante(clave, "w400")
    ruta.unlink()
    assert not ruta.is_file()

    huella = almacen._huella(clave)
    regenerado = almacen.derivar_por_huella(huella, "w400", "jpg")

    assert regenerado == ruta and ruta.is_file()
    assert almacen.derivar_por_huella(huella, "w9999", "jpg") is None
    assert almacen.derivar_por_huella("f" * 64, "w400", "jpg") is None


# ── URLs ─────────────────────────────────────────────────────────────────────

def test_url_apunta_al_disco_cuando_hay_derivado(settings):
    settings.TALLER_URL = "https://taller.example.mx/"
    clave = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="f.jpg")["id"]
    huella = almacen._huella(clave)

    ruta = almacen.url(clave, "w400")
    assert ruta == f"/medios/{huella[:2]}/{huella[2:4]}/{huella}/w400.jpg"
    assert almacen.url(clave, "w1000", absoluta=True) == (
        f"https://taller.example.mx/medios/{huella[:2]}/{huella[2:4]}/{huella}/w1000.jpg"
    )


def test_url_cae_al_proxy_mientras_la_llave_no_este_en_el_almacen():
    """Camino frío: la imagen se sigue viendo por el proxy de siempre, que la
    materializa; la siguiente vez ya sale por el camino rápido."""
    assert almacen.url("id-de-drive-sin-importar") == (
        "/catalogo/imagen/id-de-drive-sin-importar"
    )
    assert almacen.url("") == ""


# ── Compatibilidad con Drive ─────────────────────────────────────────────────

def test_leer_devuelve_la_misma_terna_que_drive(monkeypatch):
    def _explota(*_a, **_k):
        raise AssertionError("no debe tocar Drive: el archivo está en disco")

    monkeypatch.setattr("lib.google_drive.drive.descargar", _explota)
    clave = almacen.guardar_bytes(b"%PDF-1.7 x", mime="application/pdf",
                                  nombre="comprobante.pdf")["id"]

    contenido, mime, nombre = almacen.leer(clave)
    assert (contenido, mime, nombre) == (b"%PDF-1.7 x", "application/pdf",
                                         "comprobante.pdf")


def test_leer_importa_de_drive_y_lo_deja_guardado(monkeypatch):
    llamadas = {"n": 0}

    def _falso(file_id):
        llamadas["n"] += 1
        return _jpeg(), "image/jpeg", "vieja.jpg"

    monkeypatch.setattr("lib.google_drive.drive.descargar", _falso)

    contenido, mime, nombre = almacen.leer("id-viejo-de-drive")
    assert mime == "image/jpeg" and nombre == "vieja.jpg" and contenido
    assert almacen.existe("id-viejo-de-drive")
    assert almacen.meta("id-viejo-de-drive")["variantes"]  # ya tiene derivados

    almacen.leer("id-viejo-de-drive")
    assert llamadas["n"] == 1  # la segunda sale del disco


def test_leer_lanza_si_no_hay_de_donde(monkeypatch):
    def _revienta(*_a, **_k):
        raise RuntimeError("404")

    monkeypatch.setattr("lib.google_drive.drive.descargar", _revienta)

    with pytest.raises(almacen.ArchivoNoDisponible):
        almacen.leer("no-existe-en-ningun-lado")
    with pytest.raises(almacen.ArchivoNoDisponible):
        almacen.leer("")


def test_abrir_entrega_un_fileobj_para_streaming():
    clave = almacen.guardar_bytes(b"contenido largo", mime="text/plain",
                                  nombre="notas.txt")["id"]

    fileobj, mime, nombre = almacen.abrir(clave)
    try:
        assert fileobj.read() == b"contenido largo"
        assert (mime, nombre) == ("text/plain", "notas.txt")
    finally:
        fileobj.close()


def test_borrar_quita_original_y_derivados():
    clave = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="f.jpg")["id"]
    assert almacen.ruta_variante(clave, "w400").is_file()

    almacen.borrar(clave)

    assert not almacen.existe(clave)
    assert almacen.meta(clave) is None
    assert not almacen._dir_pub(clave).exists()


# ── La subida: disco primero, Drive de espejo ────────────────────────────────

class TestSubir:
    """`lib.adjuntos.subir` conserva su firma y la forma de su `data`, para que
    los ~10 puntos de subida del repo no cambien. Lo que cambia es a dónde va el
    archivo y qué pasa cuando Drive no responde."""

    def _archivo(self, nombre="foto.jpg", mime="image/jpeg", contenido=None):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(nombre, contenido or _jpeg(600, 400),
                                  content_type=mime)

    def _drive(self, monkeypatch, *, configurado=True, revienta=False):
        from lib.google_drive import drive

        monkeypatch.setattr(drive, "esta_configurado", lambda: configurado)
        monkeypatch.setattr(drive, "obtener_o_crear_subcarpeta", lambda *_a, **_k: "carp-1")

        def _sube(*_a, **_k):
            if revienta:
                raise RuntimeError("timeout")
            return {"id": "drv-99", "name": "foto.jpg", "mimeType": "image/jpeg",
                    "size": "10", "webViewLink": "https://drive.example/ver"}

        monkeypatch.setattr(drive, "subir_archivo", _sube)
        monkeypatch.setattr(drive, "subir_fileobj", _sube)

    def test_guarda_en_el_almacen_y_espeja_a_drive(self, monkeypatch):
        from lib.adjuntos import subir

        self._drive(monkeypatch)
        res = subir(self._archivo(), subcarpeta="Productos")

        assert res.ok
        # El `id` es la llave de El Almacén, no el de Drive.
        assert res.data["id"] != "drv-99"
        assert almacen.existe(res.data["id"])
        assert res.data["mimeType"] == "image/jpeg"
        assert res.data["name"] == "foto.jpg"
        # La copia de Drive queda anotada, para durabilidad fuera del servidor.
        assert res.data["espejo_drive"] == "drv-99"
        assert res.data["webViewLink"] == "https://drive.example/ver"
        assert almacen.meta(res.data["id"])["drive_file_id"] == "drv-99"

    def test_drive_caido_ya_no_tumba_la_subida(self, monkeypatch):
        """Antes, sin Drive no se podía adjuntar nada. Ahora el archivo queda
        guardado y el espejo simplemente no se hace."""
        from lib.adjuntos import subir

        self._drive(monkeypatch, revienta=True)
        res = subir(self._archivo())

        assert res.ok
        assert almacen.existe(res.data["id"])
        assert res.data["espejo_drive"] == ""
        assert "Drive no respondió" in res.data["error_espejo"]

    def test_sin_drive_conectado_tambien_guarda(self, monkeypatch):
        from lib.adjuntos import subir

        self._drive(monkeypatch, configurado=False)
        res = subir(self._archivo())

        assert res.ok and almacen.existe(res.data["id"])
        assert "no está conectado" in res.data["error_espejo"]

    def test_la_imagen_subida_queda_con_derivados_listos(self, monkeypatch):
        """Es el punto del sprint: el redimensionado se paga una vez, al subir,
        no en cada visita de cada usuario."""
        from lib.adjuntos import subir

        self._drive(monkeypatch, configurado=False)
        res = subir(self._archivo())

        assert almacen.ruta_variante(res.data["id"], "w400").is_file()
        assert almacen.url(res.data["id"]).startswith("/medios/")

    def test_sigue_rechazando_lo_que_no_se_permite(self, monkeypatch):
        from lib.adjuntos import subir

        self._drive(monkeypatch)
        res = subir(self._archivo("virus.exe", "application/x-msdownload", b"MZ"))

        assert not res.ok and "no permitido" in res.error

    def test_si_el_disco_falla_se_usa_el_id_de_drive(self, monkeypatch):
        """El Almacén lo importará solo la primera vez que alguien lo lea."""
        from lib import adjuntos

        self._drive(monkeypatch)

        def _no_se_puede(*_a, **_k):
            raise OSError("disco lleno")

        monkeypatch.setattr(almacen, "guardar_fileobj", _no_se_puede)
        res = adjuntos.subir(self._archivo())

        assert res.ok and res.data["id"] == "drv-99"

    def test_si_falla_todo_el_resultado_es_un_error_claro(self, monkeypatch):
        from lib import adjuntos

        self._drive(monkeypatch, revienta=True)

        def _no_se_puede(*_a, **_k):
            raise OSError("disco lleno")

        monkeypatch.setattr(almacen, "guardar_fileobj", _no_se_puede)
        res = adjuntos.subir(self._archivo())

        assert not res.ok and "disco lleno" in res.error


# ── Vista de respaldo (cuando El Portero no encuentra el derivado) ────────────

@pytest.mark.django_db
class TestVistaDeRespaldo:
    """En producción esta ruta casi no se ejecuta: la sirve Caddy del disco. Es
    la red para un `pub/` borrado, un restore sin derivados, o HAL sin Caddy."""

    def _url(self, clave, variante="w400", ext="jpg"):
        h = almacen._huella(clave)
        return f"/medios/{h[:2]}/{h[2:4]}/{h}/{variante}.{ext}"

    def test_sirve_el_derivado_sin_sesion(self, client, settings):
        settings.ROOT_URLCONF = "tests.urls_taller"
        clave = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="f.jpg")["id"]

        r = client.get(self._url(clave))

        assert r.status_code == 200
        assert r["Content-Type"] == "image/jpeg"
        assert r["Cache-Control"] == "public, max-age=31536000, immutable"
        assert r["X-Robots-Tag"] == "noindex"

    def test_regenera_el_derivado_que_falta(self, client, settings):
        settings.ROOT_URLCONF = "tests.urls_taller"
        clave = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="f.jpg")["id"]
        almacen.ruta_variante(clave, "w400").unlink()

        assert client.get(self._url(clave)).status_code == 200
        assert almacen.ruta_variante(clave, "w400").is_file()

    def test_huella_desconocida_es_404(self, client, settings):
        settings.ROOT_URLCONF = "tests.urls_taller"
        assert client.get(f"/medios/ab/cd/{'a' * 64}/w400.jpg").status_code == 404

    def test_rutas_invalidas_no_entran(self, client, settings):
        """El patrón sólo acepta hex, variantes conocidas y jpg/png: no hay forma
        de pedir un archivo de más arriba ni uno ajeno."""
        settings.ROOT_URLCONF = "tests.urls_taller"
        for ruta in (
            "/medios/../../etc/passwd",
            f"/medios/ab/cd/{'a' * 64}/w400.svg",
            f"/medios/ab/cd/{'a' * 64}/archivo.jpg",
            f"/medios/ab/cd/{'z' * 64}/w400.jpg",
            "/medios/ab/cd/corta/w400.jpg",
        ):
            assert client.get(ruta).status_code == 404, ruta

    def test_los_tramos_deben_coincidir_con_la_huella(self, client, settings):
        settings.ROOT_URLCONF = "tests.urls_taller"
        clave = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="f.jpg")["id"]
        h = almacen._huella(clave)
        # Misma huella, subcarpetas inventadas.
        r = client.get(f"/medios/ff/ff/{h}/w400.jpg")

        assert r.status_code == 404


class TestHeicNoSeAceptaSinDecodificador:
    """Candado: si el HEIC de un iPhone se acepta, tiene que poder pintarse.

    `lib.adjuntos.validar` mira sólo la whitelist de MIME, así que con
    `image/heic` dentro la foto se acepta, se guarda… y si Pillow no sabe abrirla
    se queda SIN derivado: el navegador no la pinta y para el usuario parece que
    la subida falló. Las dos mitades tienen que moverse juntas — o el decodificador
    está instalado, o el MIME sale de la whitelist.
    """

    RAIZ = Path(__file__).resolve().parents[1]

    def _mimes_heic(self) -> set[str]:
        from lib.adjuntos import MIME_PERMITIDOS

        return {m for m in MIME_PERMITIDOS if "hei" in m}

    def test_si_se_acepta_heic_la_dependencia_esta_fijada(self):
        aceptados = self._mimes_heic()
        if not aceptados:
            return  # nadie acepta HEIC: no hay nada que garantizar
        reqs = (self.RAIZ / "requirements.txt").read_text(encoding="utf-8")
        assert "pillow-heif==" in reqs, (
            f"`lib.adjuntos.MIME_PERMITIDOS` acepta {sorted(aceptados)} pero "
            "`requirements.txt` no fija `pillow-heif`. Sin ese decodificador la "
            "foto se guarda sin derivado y el navegador no la pinta. Instálalo o "
            "saca esos MIME de la whitelist."
        )

    def test_el_registro_del_decodificador_no_lanza(self):
        """`hay_decodificador_heic()` se llama en cada `derivar()`: pase lo que
        pase con la dependencia, tiene que devolver un bool y nunca reventar."""
        assert almacen.hay_decodificador_heic() in (True, False)


class TestElRespaldoPuedeLeerLosOriginales:
    """`archivo.sh` replica `orig/` a HAL como el usuario del host, no como root.

    `tempfile.mkstemp` crea en 0600 y `os.replace` conserva el modo, así que sin
    un `chmod` explícito el original queda legible sólo por root y el rsync falla
    con «Permission denied» en cada archivo: los medios se quedan sin respaldo
    fuera del servidor, y en silencio. Pasó en producción el 2026-08-21.
    """

    def test_el_original_es_legible_por_otros(self):
        clave = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="f.jpg")["id"]
        ruta = almacen._dir_orig(clave) / "archivo"
        modo = ruta.stat().st_mode & 0o777
        assert modo & 0o044, f"el original quedó en {oct(modo)}: el respaldo no puede leerlo"

    def test_el_meta_y_los_derivados_tambien(self):
        clave = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="f.jpg")["id"]
        for ruta in ((almacen._dir_orig(clave) / "meta.json"),
                     *(almacen._dir_pub(clave)).glob("*")):
            assert ruta.stat().st_mode & 0o044, f"{ruta.name} no es legible por el respaldo"
