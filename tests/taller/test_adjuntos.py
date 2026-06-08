"""Adjuntos a Drive desenmascarados: helper, Recados legacy y comprobante de Egreso.

La capa HTTP de Drive (`lib.google_drive`) se mockea: aquí validamos el
cableado (modelo, vistas, proxy de descarga, fallback gracioso).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# ── Helper lib.adjuntos.validar ───────────────────────────────────────────────


def test_validar_rechaza_tipo_no_permitido():
    from lib.adjuntos import validar
    archivo = SimpleUploadedFile("virus.exe", b"x", content_type="application/x-msdownload")
    assert "no permitido" in validar(archivo)


def test_validar_rechaza_tamano_excesivo():
    from lib.adjuntos import validar

    class _Grande:
        name = "enorme.png"
        size = 26 * 1024 * 1024
        content_type = "image/png"

    assert "25 MB" in validar(_Grande())


def test_validar_acepta_imagen():
    from lib.adjuntos import validar
    archivo = SimpleUploadedFile("foto.png", b"x", content_type="image/png")
    assert validar(archivo) == ""


# ── Recados legacy: subir + proxy ─────────────────────────────────────────────


def _ok(monkeypatch, data=None):
    """Mockea lib.adjuntos.subir para devolver éxito sin tocar la red."""
    from lib.adjuntos import ResultadoAdjunto
    payload = data or {"id": "drv-1", "name": "foto.png", "mimeType": "image/png", "size": "4"}
    monkeypatch.setattr("lib.adjuntos.subir", lambda archivo, subcarpeta=None: ResultadoAdjunto(ok=True, data=payload))


def test_recado_con_adjunto_crea_fila(client, usuario_factory, monkeypatch):
    from apps.recados.models import RecadoAdjunto
    autor = usuario_factory(rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    client.force_login(autor)
    _ok(monkeypatch)

    archivo = SimpleUploadedFile("foto.png", b"\x89PNG", content_type="image/png")
    resp = client.post("/recados/legacy/nuevo/", {
        "cuerpo": "Con adjunto.",
        "destinatarios_usuarios": [str(dest.pk)],
        "adjuntos": archivo,
    })
    assert resp.status_code == 302
    adj = RecadoAdjunto.objects.get()
    assert adj.drive_file_id == "drv-1"
    assert adj.nombre == "foto.png"
    assert adj.subido_por_id == autor.pk


def test_recado_adjunto_drive_caido_no_rompe_envio(client, usuario_factory, monkeypatch):
    """Si Drive falla, el recado igual se crea; el adjunto no."""
    from apps.recados.models import Recado, RecadoAdjunto

    from lib.adjuntos import ResultadoAdjunto
    autor = usuario_factory(rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    client.force_login(autor)
    monkeypatch.setattr(
        "lib.adjuntos.subir",
        lambda archivo, subcarpeta=None: ResultadoAdjunto(ok=False, error="Drive no respondió: timeout"),
    )

    archivo = SimpleUploadedFile("foto.png", b"\x89PNG", content_type="image/png")
    resp = client.post("/recados/legacy/nuevo/", {
        "cuerpo": "Drive caído.",
        "destinatarios_usuarios": [str(dest.pk)],
        "adjuntos": archivo,
    })
    assert resp.status_code == 302
    assert Recado.objects.count() == 1
    assert RecadoAdjunto.objects.count() == 0


def test_proxy_descarga_adjunto_recado(client, usuario_factory, monkeypatch):
    from apps.recados import services
    from apps.recados.models import RecadoAdjunto
    autor = usuario_factory(rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    recado = services.crear_recado(autor=autor, cuerpo="x", destinatarios_ids=[dest.pk])
    adj = RecadoAdjunto.objects.create(
        recado=recado, drive_file_id="drv-1", nombre="foto.png", mime_type="image/png",
    )
    client.force_login(autor)
    monkeypatch.setattr(
        "lib.google_drive.drive.descargar",
        lambda fid: (b"PNGBYTES", "image/png", "foto.png"),
    )
    resp = client.get(f"/recados/legacy/adjunto/{adj.pk}/")
    assert resp.status_code == 200
    assert resp.content == b"PNGBYTES"
    assert resp["Content-Type"] == "image/png"
    assert "inline" in resp["Content-Disposition"]


def test_proxy_adjunto_recado_ajeno_404(client, usuario_factory, monkeypatch):
    """Un usuario sin relación con el recado no puede bajar su adjunto."""
    from apps.recados import services
    from apps.recados.models import RecadoAdjunto
    autor = usuario_factory(rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    intruso = usuario_factory(rol="disenador", email="intruso@ej.com")
    recado = services.crear_recado(autor=autor, cuerpo="x", destinatarios_ids=[dest.pk])
    adj = RecadoAdjunto.objects.create(recado=recado, drive_file_id="drv-1", nombre="f.png")
    client.force_login(intruso)
    resp = client.get(f"/recados/legacy/adjunto/{adj.pk}/")
    assert resp.status_code == 404


# ── Tesorería: comprobante de egreso ──────────────────────────────────────────


@pytest.fixture
def centro(db):
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.get(slug="insumos-de-proyecto")


def test_egreso_con_comprobante_popula_campos(client, usuario_factory, centro, monkeypatch):
    from apps.tesoreria.models import Egreso

    from lib.adjuntos import ResultadoAdjunto
    actor = usuario_factory(rol="dueno")
    client.force_login(actor)
    monkeypatch.setattr(
        "lib.adjuntos.subir",
        lambda archivo, subcarpeta=None: ResultadoAdjunto(
            ok=True, data={"id": "cmp-1", "name": "recibo.pdf", "webViewLink": "https://drive/x"}
        ),
    )
    archivo = SimpleUploadedFile("recibo.pdf", b"%PDF-1.4", content_type="application/pdf")
    resp = client.post("/tesoreria/egresos/nuevo/", {
        "subtotal": "100", "fecha": "2026-05-19", "descripcion": "Con comprobante",
        "proveedor": "", "centro_de_costo": centro.pk, "proyecto": "",
        "pagado_por": actor.pk, "solicitado_por": "",
        "estado_pago": "pagado", "metodo": "transferencia", "moneda": "MXN",
        "comprobante": archivo,
    })
    assert resp.status_code == 302
    e = Egreso.objects.get()
    assert e.tiene_comprobante is True
    assert e.drive_file_id == "cmp-1"


def test_proxy_descarga_comprobante_egreso(client, usuario_factory, centro, monkeypatch):
    from apps.tesoreria.models import Egreso
    actor = usuario_factory(rol="dueno")
    egreso = Egreso.objects.create(
        monto=Decimal("50.00"), fecha=date.today(), descripcion="x",
        centro_de_costo=centro, creado_por=actor,
        drive_file_id="cmp-1", tiene_comprobante=True,
    )
    client.force_login(actor)
    monkeypatch.setattr(
        "lib.google_drive.drive.descargar",
        lambda fid: (b"%PDF", "application/pdf", "recibo.pdf"),
    )
    resp = client.get(f"/tesoreria/egresos/{egreso.pk}/comprobante/")
    assert resp.status_code == 200
    assert resp.content == b"%PDF"
    assert resp["Content-Type"] == "application/pdf"


def test_proxy_comprobante_sin_archivo_404(client, usuario_factory, centro):
    from apps.tesoreria.models import Egreso
    actor = usuario_factory(rol="dueno")
    egreso = Egreso.objects.create(
        monto=Decimal("50.00"), fecha=date.today(), descripcion="x",
        centro_de_costo=centro, creado_por=actor,
    )
    client.force_login(actor)
    resp = client.get(f"/tesoreria/egresos/{egreso.pk}/comprobante/")
    assert resp.status_code == 404
