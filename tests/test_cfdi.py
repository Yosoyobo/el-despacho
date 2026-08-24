"""Leer un CFDI que llegó por correo (S-NUC-Servicios, 2026-08-24).

Existe para que las facturas de proveedores se archiven solas: hoy de 36
facturas sólo 1 tiene su CFDI guardado, porque subirlas a mano nadie lo hace.

**Lo primero que cuidan estas pruebas es la seguridad**, y no es teórico: este
XML llega a un buzón al que cualquiera puede escribir, y se comprobó que el
parser de la biblioteca estándar SÍ expande entidades. Un kilobyte puede
inflarse a gigabytes.

Después, lo que rompería en silencio: confundir la factura que nos MANDAN con
la que nosotros EMITIMOS, y quedarse con un comprobante sin timbrar.
"""

from __future__ import annotations

from decimal import Decimal

from lib import cfdi

CFDI_40 = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  Version="4.0" Serie="A" Folio="1234" Fecha="2026-08-20T10:15:00"
  SubTotal="1000.00" Total="1160.00" Moneda="MXN" TipoDeComprobante="I">
  <cfdi:Emisor Rfc="SCP930101ABC" Nombre="SIMIL CUERO PLYMOUTH SA DE CV"/>
  <cfdi:Receptor Rfc="LCE240101XYZ" Nombre="LEARNING CENTER"/>
  <cfdi:Conceptos>
    <cfdi:Concepto Descripcion="Vinil textil negro 50m" Cantidad="2"/>
    <cfdi:Concepto Descripcion="Flete" Cantidad="1"/>
  </cfdi:Conceptos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"/>
  </cfdi:Complemento>
</cfdi:Comprobante>"""


# ── Seguridad: es lo primero porque el archivo viene de fuera ──────────────


def test_se_rechaza_la_bomba_de_expansion():
    """El caso que motivó la defensa. Comprobado: ElementTree expande
    entidades, así que un kilobyte se vuelve gigabytes y tumba el proceso."""
    bomba = b"""<?xml version="1.0"?>
    <!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>
    <cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4">&lol2;</cfdi:Comprobante>"""
    r = cfdi.leer(bomba)
    assert r.ok is False
    assert "entidades" in r.error.lower() or "tipo" in r.error.lower()


def test_se_rechaza_un_doctype_aunque_parezca_inofensivo():
    """Un CFDI legítimo nunca lleva DTD: rechazarlo no pierde nada."""
    r = cfdi.leer(b'<!DOCTYPE x><cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"/>')
    assert r.ok is False


def test_se_rechaza_un_archivo_gigante():
    """Medio mega ya no es una factura."""
    r = cfdi.leer(b"<x/>" + b" " * (cfdi.MAX_BYTES + 1))
    assert r.ok is False
    assert "pesa" in r.error


def test_un_archivo_vacio_no_truena():
    assert cfdi.leer(b"").ok is False


def test_basura_que_no_es_xml_no_truena():
    r = cfdi.leer(b"esto no es un xml, es el cuerpo de un correo")
    assert r.ok is False
    assert "No se pudo leer" in r.error


def test_un_xml_que_no_es_cfdi_se_rechaza():
    """Al buzón llegan adjuntos de todo tipo."""
    r = cfdi.leer(b'<?xml version="1.0"?><factura><total>100</total></factura>')
    assert r.ok is False
    assert "comprobante fiscal" in r.error


# ── Lo que tiene que leer bien ─────────────────────────────────────────────


def test_lee_un_cfdi_de_verdad():
    r = cfdi.leer(CFDI_40.encode())
    assert r.ok is True
    assert r.uuid == "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
    assert r.total == Decimal("1160.00")
    assert r.subtotal == Decimal("1000.00")
    assert r.emisor_rfc == "SCP930101ABC"
    assert r.emisor_nombre == "SIMIL CUERO PLYMOUTH SA DE CV"
    assert r.receptor_rfc == "LCE240101XYZ"
    assert r.moneda == "MXN"


def test_la_referencia_es_como_la_escribe_el_proveedor():
    assert cfdi.leer(CFDI_40.encode()).referencia == "A-1234"


def test_lee_los_conceptos():
    r = cfdi.leer(CFDI_40.encode())
    assert "Vinil textil negro 50m" in r.conceptos
    assert len(r.conceptos) == 2


def test_tambien_lee_los_viejos_de_la_version_33():
    """Siguen llegando: el buzón recibe correos con archivos de años atrás."""
    viejo = CFDI_40.replace("cfd/4", "cfd/3").replace('Version="4.0"', 'Version="3.3"')
    r = cfdi.leer(viejo.encode())
    assert r.ok is True
    assert r.total == Decimal("1160.00")


def test_un_comprobante_sin_timbrar_se_avisa():
    """Sin folio fiscal es un borrador. Se lee, pero hay que saberlo: archivarlo
    como si estuviera timbrado dejaría la contabilidad apoyada en un papel que
    el SAT no reconoce."""
    sin_timbre = CFDI_40.replace(
        '<tfd:TimbreFiscalDigital UUID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"/>', "")
    r = cfdi.leer(sin_timbre.encode())
    assert r.uuid == ""
    assert "folio fiscal" in r.error


# ── Nuestra factura o la de alguien más ────────────────────────────────────


def test_distingue_lo_que_nos_emitieron():
    """Sin esto, un CFDI que nosotros mandamos y que rebota al buzón se
    archivaría como si fuera una compra."""
    r = cfdi.leer(CFDI_40.encode())
    assert cfdi.es_nuestro(r, "LCE240101XYZ") is True
    assert cfdi.es_nuestro(r, "lce240101xyz") is True, "el RFC no distingue mayúsculas"
    assert cfdi.es_nuestro(r, "OTRO010101AAA") is False


def test_sin_rfc_propio_no_se_adivina():
    r = cfdi.leer(CFDI_40.encode())
    assert cfdi.es_nuestro(r, "") is False
