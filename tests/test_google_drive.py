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
def test_slot_google_drive_aparece_en_ajustes():
    """SLOTS_CREDENCIAL lista los slots de Drive (ya sin etiqueta 'Inactivo')."""
    from ajustes.models.credencial import SLOTS_CREDENCIAL

    claves = {c for c, _, _ in SLOTS_CREDENCIAL}
    assert "google_drive_service_account_json" in claves
    assert "google_drive_carpeta_raiz_id" in claves


@pytest.mark.django_db
def test_probar_incompleto_sin_credenciales():
    """probar() sin nada configurado avisa que falta el JSON, sin reventar."""
    from lib.google_drive import GoogleDriveWrapper

    res = GoogleDriveWrapper().probar()
    assert res["ok"] is False
    assert res["estado"] == "incompleto"


@pytest.mark.django_db
def test_probar_json_invalido():
    """JSON corrupto → estado json_invalido, mensaje amable."""
    from ajustes.models.credencial import Credencial
    from lib.google_drive import GoogleDriveWrapper

    Credencial.guardar("google_drive_service_account_json", "esto no es json")
    Credencial.guardar("google_drive_carpeta_raiz_id", "1ABC")

    res = GoogleDriveWrapper().probar()
    assert res["ok"] is False
    assert res["estado"] == "json_invalido"


@pytest.mark.django_db
def test_probar_ok_con_servicio_mockeado(monkeypatch):
    """Con un service que responde, probar() devuelve ok=True y el nombre."""
    from ajustes.models.credencial import Credencial
    from lib.google_drive import GoogleDriveWrapper

    Credencial.guardar("google_drive_service_account_json", '{"type":"service_account"}')
    Credencial.guardar("google_drive_carpeta_raiz_id", "1ABC")

    class _Exec:
        def execute(self):
            return {"id": "1ABC", "name": "El Despacho - Adjuntos"}

    class _Files:
        def get(self, **kwargs):
            return _Exec()

    class _Service:
        def files(self):
            return _Files()

    wrapper = GoogleDriveWrapper()
    # Evitamos construir el cliente real de Google: forzamos el service.
    monkeypatch.setattr(type(wrapper), "service", property(lambda self: _Service()))

    res = wrapper.probar()
    assert res["ok"] is True
    assert res["estado"] == "ok"
    assert "El Despacho - Adjuntos" in res["mensaje"]


@pytest.mark.django_db
def test_recargar_olvida_carpeta_cacheada():
    """recargar() limpia el ID de carpeta cacheado tras cambiarlo."""
    from ajustes.models.credencial import Credencial
    from lib.google_drive import GoogleDriveWrapper

    Credencial.guardar("google_drive_carpeta_raiz_id", "viejo")
    wrapper = GoogleDriveWrapper()
    assert wrapper.carpeta_raiz_id == "viejo"

    Credencial.guardar("google_drive_carpeta_raiz_id", "nuevo")
    wrapper.recargar()
    assert wrapper.carpeta_raiz_id == "nuevo"


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
