"""La importación de medios de Drive a El Almacén (S-Medios-V1, fase 5).

Lo que tiene que cumplir: guardar bajo la MISMA llave (para no migrar la base),
no repetir trabajo, no abortar por un archivo que ya no existe, y respetar el
tope para poder correrla por lotes con el sistema en uso.
"""

from __future__ import annotations

import io

import pytest
from django.core.management import call_command
from PIL import Image

from lib import almacen

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _almacen_temporal(settings, tmp_path):
    settings.MEDIOS_DIR = str(tmp_path / "medios")
    almacen.olvidar_meta()
    yield
    almacen.olvidar_meta()


def _jpeg(ancho=800, alto=600):
    buf = io.BytesIO()
    Image.new("RGB", (ancho, alto), "navy").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def drive_falso(monkeypatch):
    """Drive con dos archivos; `caidos` permite simular uno ya borrado."""
    estado = {"bajadas": [], "caidos": set()}

    def _descargar(file_id):
        estado["bajadas"].append(file_id)
        if file_id in estado["caidos"]:
            raise RuntimeError("404 en Drive")
        return _jpeg(), "image/jpeg", f"{file_id}.jpg"

    monkeypatch.setattr("lib.google_drive.drive.descargar", _descargar)
    return estado


def _servicio(nombre, imagen):
    from apps.el_catalogo.models import CategoriaServicio, Servicio

    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="Producción", defaults={"orden": 10})
    return Servicio.objects.create(nombre=nombre, categoria=cat, precio_base="100",
                                   costo="40", imagen_file_id=imagen)


def _correr(**kw):
    opciones = {"pausa": 0, "verbosity": 0}
    opciones.update(kw)
    call_command("medios_importar", **opciones)


def test_importa_bajo_la_misma_llave_que_ya_esta_en_la_base(drive_falso):
    """Es lo que hace que no haga falta ninguna migración."""
    _servicio("Playera", "ID-DRIVE-1")

    _correr()

    assert almacen.existe("ID-DRIVE-1")
    assert almacen.meta("ID-DRIVE-1")["nombre"] == "ID-DRIVE-1.jpg"
    # Y como es imagen, quedó con sus derivados listos para El Portero.
    assert almacen.url("ID-DRIVE-1").startswith("/medios/")


def test_dry_run_no_baja_nada(drive_falso):
    _servicio("Playera", "ID-DRIVE-1")

    _correr(dry_run=True)

    assert drive_falso["bajadas"] == []
    assert not almacen.existe("ID-DRIVE-1")


def test_es_idempotente(drive_falso):
    _servicio("Playera", "ID-DRIVE-1")

    _correr()
    _correr()

    assert drive_falso["bajadas"] == ["ID-DRIVE-1"]


def test_la_misma_llave_en_dos_filas_se_baja_una_vez(drive_falso):
    """La foto del catálogo puede estar congelada en varias cotizaciones."""
    _servicio("Playera", "ID-COMPARTIDO")
    _servicio("Playera 2", "ID-COMPARTIDO")

    _correr()

    assert drive_falso["bajadas"] == ["ID-COMPARTIDO"]


def test_un_archivo_borrado_de_drive_no_aborta_el_resto(drive_falso):
    drive_falso["caidos"].add("ID-ROTO")
    _servicio("Buena", "ID-BUENA")
    _servicio("Rota", "ID-ROTO")

    _correr()

    assert almacen.existe("ID-BUENA")
    assert not almacen.existe("ID-ROTO")


def test_el_limite_permite_ir_por_lotes(drive_falso):
    for i in range(4):
        _servicio(f"P{i}", f"ID-{i}")

    _correr(limite=2)

    assert len(drive_falso["bajadas"]) == 2
    # Y la siguiente corrida sigue donde quedó.
    _correr(limite=2)
    assert len(drive_falso["bajadas"]) == 4


def test_el_tipo_acota_el_grupo(drive_falso, usuario_factory):
    u = usuario_factory(rol="super_admin")
    u.avatar_drive_id = "ID-AVATAR"
    u.save(update_fields=["avatar_drive_id"])
    _servicio("Playera", "ID-FOTO")

    _correr(tipo="imagenes")

    assert almacen.existe("ID-FOTO")
    assert not almacen.existe("ID-AVATAR")


def test_los_avatares_tambien_entran(drive_falso, usuario_factory):
    u = usuario_factory(rol="super_admin")
    u.avatar_drive_id = "ID-AVATAR"
    u.save(update_fields=["avatar_drive_id"])

    _correr(tipo="avatares")

    assert almacen.existe("ID-AVATAR")


def test_el_pdf_generado_de_la_cotizacion_no_se_importa(drive_falso, cliente_factory,
                                                        proyecto_factory, usuario_factory):
    """Ese PDF lo genera Google convirtiendo nuestro HTML y nadie lo baja: la
    descarga lo vuelve a generar. Traerlo al disco no serviría de nada."""
    from apps.cotizaciones.models import Cotizacion

    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory()
    Cotizacion.objects.create(cliente=cli, proyecto=proyecto_factory(cliente=cli),
                              titulo="X", version=1, creado_por=admin,
                              pdf_file_id="ID-PDF-GENERADO")

    _correr()

    assert drive_falso["bajadas"] == []


# ── medios_derivar ───────────────────────────────────────────────────────────

def test_derivar_rehace_lo_que_falta():
    """Tras un restore que sólo trajo los originales."""
    clave = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="f.jpg")["id"]
    ruta = almacen.ruta_variante(clave, "w400")
    # Simula un `pub/` vacío: se borran los derivados y su registro en el meta.
    import shutil
    shutil.rmtree(almacen._dir_pub(clave))
    datos = almacen.meta(clave)
    almacen._escribir_meta(clave, {**datos, "variantes": {}})

    call_command("medios_derivar", verbosity=0)

    almacen.olvidar_meta()
    assert ruta.is_file()
    assert almacen.meta(clave)["variantes"]["w400"] == "w400.jpg"


def test_derivar_no_repite_lo_que_ya_esta():
    clave = almacen.guardar_bytes(_jpeg(), mime="image/jpeg", nombre="f.jpg")["id"]
    antes = almacen.ruta_variante(clave, "w400").stat().st_mtime_ns

    call_command("medios_derivar", verbosity=0)

    assert almacen.ruta_variante(clave, "w400").stat().st_mtime_ns == antes
