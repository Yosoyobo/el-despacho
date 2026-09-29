"""La papelería que el cliente sube desde La Recepción: sólo PDF o imagen (por su
contenido), sólo de SU empresa, lo que se le pide, el comprobante de una factura
y el aviso al equipo. La lectura de la CSF con El Chalán, en
`tests/taller/test_documentos_cliente.py`."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _archivo(nombre="constancia.pdf", contenido=PDF, tipo="application/pdf"):
    return SimpleUploadedFile(nombre, contenido, content_type=tipo)


@pytest.fixture
def dos(armar_cliente, acceso_de):
    a = armar_cliente("AAA", "ana@a.mx")
    b = armar_cliente("BBB", "beto@b.mx")
    a["acceso"], b["acceso"] = acceso_de(a), acceso_de(b)
    return a, b


@pytest.fixture
def sin_ia(monkeypatch):
    """La CSF no se manda a leer en estas pruebas (tienen las suyas)."""
    monkeypatch.setattr("portal.documentos._leer_csf_despues", lambda doc_id: None)


def test_subir_un_documento_lo_guarda_en_el_almacen(client, dos, entrar_como, sin_ia):
    from lib import almacen
    from portal.models import DocumentoCliente

    a, _ = dos
    entrar_como(a["acceso"])
    r = client.post("/documentos/subir/", {"tipo": "acta_constitutiva", "nota": "La del 2019",
                                           "archivo": _archivo("acta.pdf")})
    assert r.status_code == 302 and r["Location"] == "/documentos/"
    d = DocumentoCliente.objects.get()
    assert d.cliente == a["cliente"] and d.acceso == a["acceso"] and d.estado == "recibido"
    assert d.mime == "application/pdf" and d.nota == "La del 2019"
    assert almacen.leer(d.archivo)[0] == PDF
    html = client.get("/documentos/").content.decode()
    assert "Acta constitutiva" in html and "En revisión" in html


def test_solo_pasan_pdf_e_imagenes_por_su_contenido(client, dos, entrar_como, sin_ia):
    """El `content_type` lo escribe quien sube: un HTML que dice ser PDF no entra."""
    from portal.models import DocumentoCliente

    a, _ = dos
    entrar_como(a["acceso"])
    disfrazado = _archivo("csf.pdf", b"<html><script>alert(1)</script></html>", "application/pdf")
    r = client.post("/documentos/subir/", {"tipo": "csf", "archivo": disfrazado}, follow=True)
    assert "Sólo se aceptan PDF o fotos".encode() in r.content
    assert DocumentoCliente.objects.count() == 0
    # Una foto de verdad, aunque el navegador diga cualquier cosa, sí.
    client.post("/documentos/subir/", {"tipo": "identificacion",
                                       "archivo": _archivo("ine.png", PNG, "application/octet-stream")})
    assert DocumentoCliente.objects.get().mime == "image/png"


def test_sin_tipo_o_sin_archivo_no_se_guarda(client, dos, entrar_como, sin_ia):
    from portal.models import DocumentoCliente

    a, _ = dos
    entrar_como(a["acceso"])
    client.post("/documentos/subir/", {"tipo": "", "archivo": _archivo()})
    client.post("/documentos/subir/", {"tipo": "csf"})
    client.post("/documentos/subir/", {"tipo": "inventado", "archivo": _archivo()})
    assert DocumentoCliente.objects.count() == 0


def test_cada_quien_ve_y_baja_solo_lo_suyo(client, dos, entrar_como, sin_ia):
    from django.test import Client

    from portal import documentos

    a, b = dos
    doc_b = documentos.subir(b["cliente"], "csf", _archivo("DE-BETO.pdf"), acceso=b["acceso"])
    entrar_como(a["acceso"])
    assert b"DE-BETO" not in client.get("/documentos/").content
    assert client.get(f"/documentos/{doc_b.pk}/archivo/").status_code == 404

    http_b = entrar_como(b["acceso"], Client())
    r = http_b.get(f"/documentos/{doc_b.pk}/archivo/")
    assert r.status_code == 200 and r.content == PDF
    assert r["Content-Disposition"].startswith("attachment") and r["X-Content-Type-Options"] == "nosniff"


def test_el_mismo_archivo_de_dos_clientes_conserva_cada_nombre(dos, sin_ia):
    """El Almacén guarda por contenido: el mismo PDF es un solo archivo. El nombre
    que ve cada cliente es el que él subió."""
    from portal import documentos

    a, b = dos
    da = documentos.subir(a["cliente"], "csf", _archivo("de-ana.pdf"), acceso=a["acceso"])
    db = documentos.subir(b["cliente"], "csf", _archivo("de-beto.pdf"), acceso=b["acceso"])
    assert da.archivo == db.archivo
    assert (da.nombre_archivo, db.nombre_archivo) == ("de-ana.pdf", "de-beto.pdf")


def test_sin_sesion_no_se_sube_ni_se_ve(client, dos, sin_ia):
    r = client.post("/documentos/subir/", {"tipo": "csf", "archivo": _archivo()})
    assert r.status_code == 302 and r["Location"].startswith("/entrar/")
    assert client.get("/documentos/").status_code == 302


def test_el_comprobante_se_liga_solo_a_una_factura_suya(client, dos, entrar_como, sin_ia):
    from portal.models import DocumentoCliente

    a, b = dos
    entrar_como(a["acceso"])
    r = client.post("/documentos/subir/", {"tipo": "comprobante_pago", "factura": a["factura"].pk,
                                           "volver": "factura", "archivo": _archivo("pago.pdf")})
    assert r["Location"] == f"/facturas/{a['factura'].pk}/"
    assert DocumentoCliente.objects.get().factura == a["factura"]
    # La factura del otro cliente no se liga (y no se entera de que existe).
    client.post("/documentos/subir/", {"tipo": "comprobante_pago", "factura": b["factura"].pk,
                                       "archivo": _archivo("pago2.pdf")})
    assert DocumentoCliente.objects.filter(factura=b["factura"]).count() == 0
    html = client.get(f"/facturas/{a['factura'].pk}/").content.decode()
    assert "Subir comprobante" in html and "pago.pdf" in html


def test_el_comprobante_no_registra_el_cobro(client, dos, entrar_como, sin_ia):
    """Decisión de Oscar: «sólo avisa». El saldo no se mueve."""
    from apps.tesoreria.models import Ingreso

    a, _ = dos
    antes = Ingreso.objects.count()
    entrar_como(a["acceso"])
    client.post("/documentos/subir/", {"tipo": "comprobante_pago", "factura": a["factura"].pk,
                                       "archivo": _archivo("pago.pdf")})
    assert Ingreso.objects.count() == antes


def test_lo_que_se_pide_y_como_va(client, dos, entrar_como, sin_ia, usuario_factory):
    from portal import documentos
    from portal.models import ConfiguracionPortal

    cfg = ConfiguracionPortal.obtener()
    cfg.documentos_requeridos = ["csf", "acta_constitutiva", "poder_notarial"]
    cfg.save()
    a, _ = dos
    csf = documentos.subir(a["cliente"], "csf", _archivo(), acceso=a["acceso"])
    acta = documentos.subir(a["cliente"], "acta_constitutiva", _archivo(), acceso=a["acceso"])
    documentos.revisar(csf, usuario_factory(rol="super_admin"), aprobar=True)
    documentos.revisar(acta, None, aprobar=False, motivo="Le faltan hojas")
    estados = {p.tipo: p.estado for p in documentos.pendientes_de(a["cliente"])}
    assert estados == {"csf": "listo", "acta_constitutiva": "rechazado", "poder_notarial": "falta"}

    entrar_como(a["acceso"])
    inicio = client.get("/").content.decode()
    assert "Nos falta papelería" in inicio and "Poder del representante legal" in inicio
    html = client.get("/documentos/").content.decode()
    assert "Le faltan hojas" in html and "Volver a subir" in html

    # Uno nuevo del mismo tipo manda sobre el rechazado.
    documentos.subir(a["cliente"], "acta_constitutiva", _archivo(), acceso=a["acceso"])
    assert {p.tipo: p.estado for p in documentos.pendientes_de(a["cliente"])}["acta_constitutiva"] == "revision"


def test_apagados_en_la_gerencia_no_hay_seccion(client, dos, entrar_como, sin_ia):
    from portal.models import ConfiguracionPortal

    cfg = ConfiguracionPortal.obtener()
    cfg.documentos_activo = False
    cfg.save()
    a, _ = dos
    entrar_como(a["acceso"])
    assert b'href="/documentos/"' not in client.get("/").content
    assert client.get("/documentos/").status_code == 404
    assert client.post("/documentos/subir/", {"tipo": "csf", "archivo": _archivo()}).status_code == 404


def test_subir_tiene_freno(client, dos, entrar_como, sin_ia, monkeypatch):
    from lib.errors import RateLimitExcedido
    from portal.models import DocumentoCliente

    a, _ = dos
    entrar_como(a["acceso"])

    def _lleno(*a, **k):
        raise RateLimitExcedido("lleno")

    monkeypatch.setattr("apps.portal_cliente.views.intentar", _lleno)
    r = client.post("/documentos/subir/", {"tipo": "csf", "archivo": _archivo()}, follow=True)
    assert b"muchos archivos" in r.content
    assert DocumentoCliente.objects.count() == 0


def test_el_equipo_se_entera_y_el_comprobante_le_llega_a_quien_cobra(dos, usuario_factory, monkeypatch, sin_ia):
    from django.db import transaction

    from cuentas.models import PermisoUsuario
    from portal import documentos

    monkeypatch.setattr(transaction, "on_commit", lambda fn, using=None, robust=False: fn())
    monkeypatch.setattr("lib.tareas_fondo.ejecutar_en_fondo", lambda fn, *a, **k: fn(*a, **k))
    avisados = []
    monkeypatch.setattr("lib.interfono.enviar_a_usuario",
                        lambda u, **kw: avisados.append((u.email, kw["titulo"], kw["categoria"])))
    revisa = usuario_factory(rol="miembro", email="revisa@lc.mx")
    PermisoUsuario.objects.create(usuario=revisa, modulo="recepcion", permiso="documentos", activo=True)
    cobra = usuario_factory(rol="miembro", email="cobra@lc.mx")
    PermisoUsuario.objects.create(usuario=cobra, modulo="facturacion", permiso="cobrar", activo=True)

    a, _ = dos
    documentos.subir(a["cliente"], "acta_constitutiva", _archivo(), acceso=a["acceso"])
    assert {e for e, _, _ in avisados} >= {"revisa@lc.mx"} and "cobra@lc.mx" not in {e for e, _, _ in avisados}
    avisados.clear()
    documentos.subir(a["cliente"], "comprobante_pago", _archivo(), acceso=a["acceso"], factura=a["factura"])
    assert {"revisa@lc.mx", "cobra@lc.mx"} <= {e for e, _, _ in avisados}
    assert all(c == "portal_documentos" for _, _, c in avisados)
    assert all("Comprobante" in t for _, t, _ in avisados)


def test_lo_que_sube_el_equipo_no_le_avisa_al_equipo(dos, usuario_factory, monkeypatch, sin_ia):
    from django.db import transaction

    from portal import documentos

    monkeypatch.setattr(transaction, "on_commit", lambda fn, using=None, robust=False: fn())
    avisados = []
    monkeypatch.setattr("lib.interfono.enviar_a_usuario", lambda u, **kw: avisados.append(u))
    a, _ = dos
    documentos.subir(a["cliente"], "csf", _archivo(), usuario=usuario_factory(rol="super_admin"))
    assert avisados == []


def test_una_csf_vencida_se_le_avisa_al_cliente(client, dos, entrar_como, sin_ia):
    from portal import documentos

    a, _ = dos
    d = documentos.subir(a["cliente"], "csf", _archivo(), acceso=a["acceso"])
    d.ia_estado = "lista"
    d.ia = {"es_csf": True, "datos": {"rfc": "AAA010101AAA"},
            "vigencia": {"fecha_emision": "2026-01-15", "dias": 257, "limite": 30, "vigente": False}}
    d.save()
    entrar_como(a["acceso"])
    html = client.get("/documentos/").content.decode()
    assert "pedimos una de máximo 30 días" in html


def test_toda_pagina_de_documentos_lleva_el_footer_noko(client, dos, entrar_como):
    a, _ = dos
    entrar_como(a["acceso"])
    html = client.get("/documentos/").content.decode()
    assert 'href="https://devs.noko.mx"' in html and "NoKo Devs" in html
