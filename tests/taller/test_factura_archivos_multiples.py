"""Varios archivos a la vez en una factura (ticket Oscar 14-oct-2026).

Antes: la factura guardaba UN PDF y UN XML; un segundo PDF (o cualquier otro
archivo) se descartaba en silencio. Ahora el primer PDF/XML son el CFDI y todo
lo demás queda como adjunto, cada archivo se valida por separado y uno malo no
tumba a los demás.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _almacen_temporal(settings, tmp_path):
    from lib import almacen

    settings.MEDIOS_DIR = str(tmp_path / "medios")
    almacen.olvidar_meta()
    yield
    almacen.olvidar_meta()


@pytest.fixture(autouse=True)
def _sin_drive(monkeypatch):
    """El espejo de Drive no es lo que se prueba aquí."""
    monkeypatch.setattr("lib.adjuntos._espejar_en_drive", lambda *a, **k: (None, "sin drive"))


@pytest.fixture
def fac(cliente_factory, usuario_factory):
    from apps.facturacion.models import Factura, FacturaItem

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    f = Factura.objects.create(cliente=cli, titulo="Servicios", creado_por=autor)
    FacturaItem.objects.create(
        factura=f, orden=0, descripcion="Diseño",
        cantidad=Decimal("1"), unidad="pieza", precio_unitario=Decimal("1000.00"),
    )
    return f


def _pdf(nombre="a.pdf", cuerpo=b"%PDF-1.4 a"):
    return SimpleUploadedFile(nombre, cuerpo, content_type="application/pdf")


def _xml(nombre="a.xml", cuerpo=b"<cfdi/>"):
    return SimpleUploadedFile(nombre, cuerpo, content_type="text/xml")


def _png(nombre="foto.png", cuerpo=b"\x89PNG-fake-1"):
    return SimpleUploadedFile(nombre, cuerpo, content_type="image/png")


# ── El servicio ───────────────────────────────────────────────────────────


def test_dos_pdfs_juntos_uno_es_cfdi_y_el_otro_adjunto(fac):
    from apps.facturacion import services

    res = services.almacenar_archivos(
        fac, [_pdf("cfdi.pdf", b"%PDF uno"), _pdf("complemento.pdf", b"%PDF dos")],
        actor=fac.creado_por)
    assert res["ok"] and not res["errores"]
    fac.refresh_from_db()
    assert fac.pdf_file_id  # el primero quedó como CFDI
    assert [a.nombre for a in fac.adjuntos.all()] == ["complemento.pdf"]


def test_pdf_xml_e_imagenes_en_una_sola_subida(fac):
    from apps.facturacion import services

    res = services.almacenar_archivos(
        fac, [_pdf(), _xml(), _png("a.png", b"\x89PNG-1"), _png("b.png", b"\x89PNG-2")],
        actor=fac.creado_por)
    assert res["ok"], res
    fac.refresh_from_db()
    assert fac.pdf_file_id and fac.xml_file_id
    assert {a.nombre for a in fac.adjuntos.all()} == {"a.png", "b.png"}


def test_con_el_cfdi_ya_cargado_un_pdf_nuevo_no_lo_pisa(fac):
    from apps.facturacion import services

    services.almacenar_archivos(fac, [_pdf("original.pdf", b"%PDF original")])
    fac.refresh_from_db()
    original = fac.pdf_file_id
    services.almacenar_archivos(fac, [_pdf("otro.pdf", b"%PDF otro")])
    fac.refresh_from_db()
    assert fac.pdf_file_id == original  # no se pisó en silencio
    assert [a.nombre for a in fac.adjuntos.all()] == ["otro.pdf"]


def test_un_archivo_malo_no_tumba_a_los_demas_y_el_error_lleva_su_nombre(fac):
    from apps.facturacion import services

    malo = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/x-msdownload")
    res = services.almacenar_archivos(fac, [_png("ok1.png", b"\x89PNG-ok1"), malo,
                                            _png("ok2.png", b"\x89PNG-ok2")])
    assert not res["ok"]  # hubo un error...
    assert any("virus.exe" in e for e in res["errores"])
    assert {a.nombre for a in fac.adjuntos.all()} == {"ok1.png", "ok2.png"}  # ...y los demás sí


def test_archivo_de_mas_de_25mb_se_rechaza_por_su_cuenta(fac):
    from apps.facturacion import services

    enorme = _png("enorme.png", b"x")
    enorme.size = 26 * 1024 * 1024
    res = services.almacenar_archivos(fac, [enorme, _png("chico.png", b"\x89PNG-c")])
    assert any("enorme.png" in e and "25 MB" in e for e in res["errores"])
    assert [a.nombre for a in fac.adjuntos.all()] == ["chico.png"]


def test_tope_de_archivos_por_envio(fac):
    from apps.facturacion import services

    n = services.MAX_ARCHIVOS_POR_ENVIO + 2
    archivos = [_png(f"{i}.png", f"\x89PNG-{i}".encode()) for i in range(n)]
    res = services.almacenar_archivos(fac, archivos)
    assert fac.adjuntos.count() == services.MAX_ARCHIVOS_POR_ENVIO
    assert any("por vez" in e for e in res["errores"])


# ── Las vistas ────────────────────────────────────────────────────────────


def test_modal_cfdi_acepta_otros_archivos_varios(client, fac):
    client.force_login(fac.creado_por)
    r = client.post(
        f"/facturacion/{fac.pk}/cfdi/",
        data={"otros": [_png("x.png", b"\x89PNG-x"), _png("y.png", b"\x89PNG-y")]},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    assert {a.nombre for a in fac.adjuntos.all()} == {"x.png", "y.png"}


def test_descargar_y_quitar_adjunto(client, fac):
    from apps.facturacion import services

    services.almacenar_archivos(fac, [_png("foto.png", b"\x89PNG-descarga")])
    adj = fac.adjuntos.get()
    client.force_login(fac.creado_por)
    r = client.get(f"/facturacion/{fac.pk}/adjuntos/{adj.pk}/")
    assert r.status_code == 200 and r.content == b"\x89PNG-descarga"

    # el detalle los lista con su liga
    d = client.get(f"/facturacion/{fac.pk}/")
    assert "foto.png" in d.content.decode()
    assert f"/facturacion/{fac.pk}/adjuntos/{adj.pk}/" in d.content.decode()

    # GET no quita; POST sí
    assert client.get(f"/facturacion/{fac.pk}/adjuntos/{adj.pk}/quitar/").status_code == 405
    r = client.post(f"/facturacion/{fac.pk}/adjuntos/{adj.pk}/quitar/")
    assert r.status_code == 302
    assert fac.adjuntos.count() == 0


def test_un_adjunto_de_otra_factura_no_se_puede_pedir_por_esta(client, fac, cliente_factory):
    from apps.facturacion import services
    from apps.facturacion.models import Factura

    services.almacenar_archivos(fac, [_png("foto.png", b"\x89PNG-ajeno")])
    adj = fac.adjuntos.get()
    otra = Factura.objects.create(cliente=fac.cliente, titulo="Otra", creado_por=fac.creado_por)
    client.force_login(fac.creado_por)
    assert client.get(f"/facturacion/{otra.pk}/adjuntos/{adj.pk}/").status_code == 404
    assert client.post(f"/facturacion/{otra.pk}/adjuntos/{adj.pk}/quitar/").status_code == 404


def test_quitar_adjunto_exige_permiso(client, fac, usuario_factory):
    from apps.facturacion import services

    services.almacenar_archivos(fac, [_png("foto.png", b"\x89PNG-perm")])
    adj = fac.adjuntos.get()
    sin_permiso = usuario_factory(rol="disenador")
    client.force_login(sin_permiso)
    r = client.post(f"/facturacion/{fac.pk}/adjuntos/{adj.pk}/quitar/")
    assert r.status_code in (403, 302)
    assert fac.adjuntos.count() == 1


def test_el_form_de_factura_permite_elegir_varios():
    from pathlib import Path

    html = Path(__file__).resolve().parents[2] / "el-taller/templates/facturacion/factura_form.html"
    assert 'name="cfdi_archivos" multiple' in html.read_text()


def test_el_form_de_edicion_guarda_dos_pdfs_y_uno_se_puede_quitar(client, fac):
    """El camino real del ticket: dos PDFs en el mismo campo del form."""
    client.force_login(fac.creado_por)
    base = {
        "folio_numero": fac.folio_numero or "", "porcentaje_a_facturar": "100",
        "cliente": fac.cliente_id, "proyecto": "", "cotizacion_origen": "",
        "concepto": "Lona", "estado": "borrador",
        "fecha_emision": fac.fecha_emision.isoformat(),
        "fecha_vencimiento": fac.fecha_vencimiento.isoformat(),
        "moneda": "MXN", "descuento_global_porcentaje": "0", "notas": "", "terminos": "",
        "items-TOTAL_FORMS": "0", "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
    }
    r = client.post(f"/facturacion/{fac.pk}/editar/", {
        **base, "cfdi_archivos": [_pdf("uno.pdf", b"%PDF uno"), _pdf("dos.pdf", b"%PDF dos")],
    })
    assert r.status_code == 302
    fac.refresh_from_db()
    assert fac.pdf_file_id
    adj = fac.adjuntos.get()
    assert adj.nombre == "dos.pdf"

    r = client.post(f"/facturacion/{fac.pk}/editar/", {**base, "adjunto_borrar": [str(adj.pk)]})
    assert r.status_code == 302
    assert fac.adjuntos.count() == 0
