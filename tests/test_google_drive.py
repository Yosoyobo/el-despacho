"""S2b.1.5 — andamiaje wrapper Google Drive (no operativo todavía)."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_wrapper_drive_sin_credenciales_lanza_no_configurado():
    """Si los slots están vacíos, `drive.service` lanza NoConfiguradoError."""
    from lib.google_drive import GoogleDriveWrapper, NoConfiguradoError

    wrapper = GoogleDriveWrapper()
    assert wrapper.esta_configurado() is False
    with pytest.raises(NoConfiguradoError):
        _ = wrapper.service
    with pytest.raises(NoConfiguradoError):
        _ = wrapper.carpeta_raiz_id


@pytest.mark.django_db
def test_wrapper_drive_metodos_lanzan_notimplemented():
    """Subir / crear / obtener_o_crear lanzan NotImplementedError claro."""
    from lib.google_drive import drive

    with pytest.raises(NotImplementedError, match="S2b.1b"):
        drive.subir_archivo("/tmp/x", "x", "carpeta", "image/png")
    with pytest.raises(NotImplementedError, match="S2b.1b"):
        drive.crear_carpeta("nueva", "padre")
    with pytest.raises(NotImplementedError, match="S2b.1b"):
        drive.obtener_o_crear_carpeta("nueva", "padre")


@pytest.mark.django_db
def test_slot_google_drive_aparece_en_ajustes_y_marcado_inactivo():
    """SLOTS_CREDENCIAL lista los slots de Drive con etiqueta 'Inactivo'."""
    from ajustes.models.credencial import SLOTS_CREDENCIAL

    claves = {c for c, _, _ in SLOTS_CREDENCIAL}
    assert "google_drive_service_account_json" in claves
    assert "google_drive_carpeta_raiz_id" in claves

    etiquetas = {c: e for c, e, _ in SLOTS_CREDENCIAL}
    assert "Inactivo" in etiquetas["google_drive_service_account_json"]
    assert "Inactivo" in etiquetas["google_drive_carpeta_raiz_id"]


def test_dependencias_google_importables():
    """Las libs están instaladas — el import no debe fallar."""
    import googleapiclient.discovery  # noqa: F401
    from google.oauth2 import service_account  # noqa: F401


@pytest.mark.django_db
def test_wrapper_drive_lee_credenciales_de_boveda_si_existen():
    """Con credenciales pegadas, `esta_configurado` retorna True."""
    from ajustes.models.credencial import Credencial
    from lib.google_drive import GoogleDriveWrapper

    Credencial.guardar("google_drive_service_account_json", '{"type":"service_account"}')
    Credencial.guardar("google_drive_carpeta_raiz_id", "1ABCdef")

    wrapper = GoogleDriveWrapper()
    assert wrapper.esta_configurado() is True
    assert wrapper.carpeta_raiz_id == "1ABCdef"


def test_doc_setup_drive_existe():
    """La documentación de activación está en su sitio."""
    from pathlib import Path

    doc = Path(__file__).resolve().parent.parent / "docs" / "SETUP_GOOGLE_DRIVE.md"
    assert doc.exists(), "docs/SETUP_GOOGLE_DRIVE.md no existe"
    contenido = doc.read_text()
    # 8 pasos numerados
    for paso in range(1, 9):
        assert f"Paso {paso}" in contenido, f"Falta Paso {paso}"


def test_form_recados_tooltip_apunta_a_doc_setup():
    """El botón 📎 del form de Recados tiene tooltip que linkea al doc."""
    from pathlib import Path

    form = Path(__file__).resolve().parent.parent / "el-taller" / "templates" / "recados" / "form.html"
    contenido = form.read_text()
    assert "📎" in contenido
    assert "SETUP_GOOGLE_DRIVE" in contenido
