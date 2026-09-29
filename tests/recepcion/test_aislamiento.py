"""EL candado del portal: un cliente ve lo SUYO y nada de otro cliente.

Dos clientes completos (proyecto con producto, cotización enviada con PDF,
factura con PDF y XML). Se entra como el contacto de A y se intenta todo lo de
B por la URL: cada pantalla, cada descarga y cada botón. Todo tiene que dar
404, ningún documento de B puede salir de Drive y nada de B se puede aprobar.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def dos(armar_cliente, acceso_de, entrar_como, client, monkeypatch):
    a = armar_cliente("AAA", "ana@a.mx")
    b = armar_cliente("BBB", "beto@b.mx")
    a["acceso"] = acceso_de(a)
    b["acceso"] = acceso_de(b)
    bajados: list[str] = []

    def _descargar(file_id):
        bajados.append(file_id)
        return (b"%PDF-1.4 contenido", "application/pdf", "x.pdf")

    monkeypatch.setattr("lib.google_drive.drive.descargar", _descargar)
    entrar_como(a["acceso"])
    return {"a": a, "b": b, "bajados": bajados, "http": client}


PANTALLAS = ["/", "/proyectos/", "/cotizaciones/", "/facturas/"]


@pytest.mark.parametrize("ruta", PANTALLAS)
def test_las_listas_traen_lo_mio_y_nada_del_otro(dos, ruta):
    html = dos["http"].get(ruta).content.decode()
    assert "BBB" not in html, f"{ruta} enseña algo del otro cliente"
    assert "EMPRESA-AAA" in html


def test_cada_detalle_del_otro_cliente_es_404(dos):
    b, http = dos["b"], dos["http"]
    for ruta in (
        f"/proyectos/{b['proyecto'].codigo}/",
        f"/cotizaciones/{b['cotizacion'].pk}/",
        f"/facturas/{b['factura'].pk}/",
    ):
        r = http.get(ruta)
        assert r.status_code == 404, ruta
        assert b"BBB" not in r.content


def test_ninguna_descarga_del_otro_cliente_sale_de_drive(dos):
    b, http = dos["b"], dos["http"]
    for ruta in (
        f"/cotizaciones/{b['cotizacion'].pk}/pdf/",
        f"/facturas/{b['factura'].pk}/pdf/",
        f"/facturas/{b['factura'].pk}/xml/",
    ):
        assert http.get(ruta).status_code == 404, ruta
    assert dos["bajados"] == [], "se pidió a Drive un documento de otro cliente"


def test_las_descargas_propias_si_salen(dos):
    a, http = dos["a"], dos["http"]
    r = http.get(f"/cotizaciones/{a['cotizacion'].pk}/pdf/")
    assert r.status_code == 200
    assert r["Content-Disposition"].startswith("attachment")
    assert http.get(f"/facturas/{a['factura'].pk}/xml/").status_code == 200
    assert dos["bajados"] == ["drive-cot-AAA", "drive-xml-AAA"]


def test_no_se_puede_aprobar_ni_rechazar_la_cotizacion_del_otro(dos):
    b, http = dos["b"], dos["http"]
    cot = b["cotizacion"]
    r = http.post(f"/cotizaciones/{cot.pk}/aprobar/", {"nombre": "Ana", "acepto": "1"})
    assert r.status_code == 404
    r = http.post(f"/cotizaciones/{cot.pk}/rechazar/", {"nombre": "Ana", "motivo": "no"})
    assert r.status_code == 404
    cot.refresh_from_db()
    assert cot.estado == "enviada" and not cot.aprobada_por_nombre and not cot.motivo_rechazo


def test_el_cliente_sale_de_la_sesion_no_de_la_url(dos):
    """Aunque se cuele un `cliente` en la URL o el formulario, manda la sesión."""
    b, http = dos["b"], dos["http"]
    html = http.get(f"/?cliente={b['cliente'].pk}").content.decode()
    assert "BBB" not in html
    r = http.post(f"/cotizaciones/{b['cotizacion'].pk}/aprobar/",
                  {"nombre": "Ana", "acepto": "1", "cliente": b["cliente"].pk})
    assert r.status_code == 404


def test_lo_interno_no_sale_nunca(dos):
    """Costos, notas internas de la línea y de la cotización: nada de eso se pinta."""
    a, http = dos["a"], dos["http"]
    for ruta in (f"/proyectos/{a['proyecto'].codigo}/", f"/cotizaciones/{a['cotizacion'].pk}/",
                 "/proyectos/", "/"):
        html = http.get(ruta).content.decode()
        assert "NOTA-INTERNA-AAA" not in html, ruta
        assert "NOTAS-COT-AAA" not in html, ruta
        assert "37.00" not in html and "$37" not in html, f"{ruta} enseña el costo"
    detalle = http.get(f"/proyectos/{a['proyecto'].codigo}/").content.decode()
    assert "PRODUCTO-AAA" in detalle and "150" in detalle


def test_lo_que_no_le_toca_ver_no_sale_ni_de_su_cliente(dos, proyecto_factory):
    """Archivados, cancelados, cotizaciones armadas o anuladas, facturas en
    borrador o canceladas: no se ven aunque sean de su cliente."""
    from apps.cotizaciones.models import Cotizacion
    from apps.facturacion.models import Factura

    a, http = dos["a"], dos["http"]
    c = a["cliente"]
    proyecto_factory(cliente=c, nombre="OCULTO-ARCHIVADO", archivado=True)
    proyecto_factory(cliente=c, nombre="OCULTO-CANCELADO", estado="cancelado")
    Cotizacion.objects.create(cliente=c, titulo="OCULTA-ARMADA", estado="generada")
    Cotizacion.objects.create(cliente=c, titulo="OCULTA-ANULADA", estado="anulada",
                              enviada_en="2026-09-01T12:00:00Z")
    Factura.objects.create(cliente=c, concepto="OCULTA-BORRADOR", estado="borrador")
    Factura.objects.create(cliente=c, concepto="OCULTA-CANCELADA", estado="cancelada",
                           pdf_file_id="x")
    todo = "".join(http.get(r).content.decode() for r in PANTALLAS)
    assert "OCULTO-" not in todo and "OCULTA-" not in todo


def test_sin_sesion_toda_pantalla_manda_a_entrar(armar_cliente):
    """Cerrado por default: cada ruta del portal que no es pública redirige."""
    from django.test import Client
    from django.urls import get_resolver

    datos = armar_cliente("CCC", "c@c.mx")
    anonimo = Client()
    rutas = ["/", "/proyectos/", f"/proyectos/{datos['proyecto'].codigo}/",
             "/cotizaciones/", f"/cotizaciones/{datos['cotizacion'].pk}/",
             f"/cotizaciones/{datos['cotizacion'].pk}/pdf/",
             "/facturas/", f"/facturas/{datos['factura'].pk}/",
             f"/facturas/{datos['factura'].pk}/pdf/", f"/facturas/{datos['factura'].pk}/xml/"]
    for ruta in rutas:
        r = anonimo.get(ruta)
        assert r.status_code == 302 and r["Location"].startswith("/entrar/"), ruta
    r = anonimo.post(f"/cotizaciones/{datos['cotizacion'].pk}/aprobar/", {"nombre": "x", "acepto": "1"})
    assert r.status_code == 302 and r["Location"].startswith("/entrar/")

    # Y ninguna ruta nueva nace pública por accidente: cada patrón del urlconf
    # es de la lista de públicas o exige sesión.
    from apps.portal_cliente.middleware import es_publica

    publicas = {str(p.pattern) for p in get_resolver().url_patterns if es_publica("/" + str(p.pattern))}
    assert publicas == {
        "ping", "salud", "sistema/aviso-deploy/", "sistema/aviso-deploy/semaforo/",
        "entrar/", "entrar/<str:token>/", "auth/google/iniciar", "auth/google/callback",
        "legal/privacidad", "legal/terminos",
    }
