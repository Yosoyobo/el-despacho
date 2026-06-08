"""S-Adjuntos-UI — el detalle admin del Buzón (La Gerencia) ahora muestra los
adjuntos en bottom pop-over + proxy de descarga propio (cross-domain)."""

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


@pytest.fixture
def mensaje_con_adjuntos(db, usuario_factory):
    from buzon.models import MensajeBuzon, MensajeBuzonAdjunto
    autor = usuario_factory(rol="disenador")
    msg = MensajeBuzon.objects.create(
        autor=autor, tipo="problema", asunto="Con archivo", cuerpo="z" * 30,
    )
    MensajeBuzonAdjunto.objects.create(
        mensaje=msg, drive_file_id="gimg", nombre="pantalla.png",
        mime_type="image/png", tamano_bytes=10, subido_por=autor,
    )
    return msg


def test_admin_detalle_muestra_popover(client, usuario_factory, mensaje_con_adjuntos):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/buzon/{mensaje_con_adjuntos.pk}/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "data-adjuntos-popover-trigger" in html
    adj = mensaje_con_adjuntos.adjuntos.first()
    # El proxy es el de Gerencia, no el del Taller.
    assert f"/buzon/adjunto/{adj.pk}/" in html
    assert "data-lightbox=" in html


def test_adjunto_proxy_requiere_admin(client, usuario_factory, mensaje_con_adjuntos):
    adj = mensaje_con_adjuntos.adjuntos.first()
    client.force_login(usuario_factory(rol="disenador"))
    resp = client.get(f"/buzon/adjunto/{adj.pk}/")
    # requires_role devuelve 403 a roles no admin en La Gerencia.
    assert resp.status_code == 403


def test_adjunto_proxy_sirve_archivo(client, usuario_factory, mensaje_con_adjuntos, monkeypatch):
    adj = mensaje_con_adjuntos.adjuntos.first()
    from lib import google_drive
    monkeypatch.setattr(
        google_drive.drive, "descargar",
        lambda fid: (b"PNGDATA", "image/png", "pantalla.png"),
    )
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/buzon/adjunto/{adj.pk}/")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "image/png"
    assert resp["Content-Disposition"].startswith("inline")
    assert resp.content == b"PNGDATA"
