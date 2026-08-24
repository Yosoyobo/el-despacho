"""Los CFDI que entran solos por correo (S-NUC-Servicios, 2026-08-24).

El número que motivó esto: **de 36 facturas, sólo 1 tenía su CFDI archivado**.
El lugar donde guardarlo existe desde julio; lo que no ocurre es que alguien lo
baje del PAC y lo suba uno por uno.

Lo que estas pruebas cuidan, en orden de lo que dolería:

1. Que **no se ligue a ciegas**. Si dos facturas coinciden, adivinar dejaría la
   contabilidad apoyada en una suposición que nadie revisó. Peor que no ligar.
2. Que **reenviar el mismo correo no archive dos copias**.
3. Que **una factura de proveedor no se cuele como ingreso nuestro**.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db

RFC_NUESTRO = "LCE240101XYZ"
RFC_CLIENTE = "OPT150505AB1"


def _xml(*, total="1160.00", uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
         emisor=RFC_NUESTRO, receptor=RFC_CLIENTE, serie="A", folio="1234") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  Version="4.0" Serie="{serie}" Folio="{folio}" Fecha="2026-08-20T10:15:00"
  SubTotal="1000.00" Total="{total}" Moneda="MXN">
  <cfdi:Emisor Rfc="{emisor}" Nombre="LEARNING CENTER"/>
  <cfdi:Receptor Rfc="{receptor}" Nombre="OPTIMIST SA DE CV"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="{uuid}"/>
  </cfdi:Complemento>
</cfdi:Comprobante>""".encode()


@pytest.fixture(autouse=True)
def _somos_nosotros(monkeypatch):
    """El RFC del despacho, que en producción vive en La Bóveda."""
    from apps.facturacion import ingesta_cfdi

    monkeypatch.setattr(ingesta_cfdi, "_rfc_propio", lambda: RFC_NUESTRO)


@pytest.fixture(autouse=True)
def _sin_drive(monkeypatch):
    """Guardar el archivo es best-effort y aquí no interesa."""
    from apps.facturacion import ingesta_cfdi

    monkeypatch.setattr(ingesta_cfdi, "_guardar_archivo", lambda *a, **k: None)


def _cliente_con_rfc(rfc=RFC_CLIENTE):
    from apps.la_cartera.models import Cliente

    return Cliente.objects.create(razon_social="Optimist", rfc=rfc, activo=True)


def _factura(cliente, autor, precio="1000.00", tasa=None):
    from apps.facturacion.models import Factura, FacturaImpuesto, FacturaItem

    fac = Factura.objects.create(cliente=cliente, titulo="Factura",
                                 regimen_fiscal="iva", creado_por=autor)
    FacturaItem.objects.create(factura=fac, orden=0, descripcion="Servicio",
                               cantidad=Decimal("1"), unidad="pz",
                               precio_unitario=Decimal(precio))
    if tasa:
        FacturaImpuesto.objects.create(factura=fac, tasa=tasa)
    return fac


@pytest.fixture
def iva():
    from ajustes.models.tasa import TasaImpositiva

    return TasaImpositiva.objects.create(
        nombre="IVA 16%", porcentaje=Decimal("16.00"), tipo="trasladado",
        aplicable_default=True, activa=True, orden=10)


# ── Lo que tiene que pasar solo ────────────────────────────────────────────


def test_una_sola_coincidencia_se_liga_sola(usuario_factory, iva):
    """El caso feliz: hay UNA factura de ese cliente por ese monto sin
    comprobante. Es inequívoco, así que se liga sin preguntar."""
    from apps.facturacion import ingesta_cfdi
    from apps.facturacion.models import ESTADO_LIGADO

    autor = usuario_factory(rol="super_admin")
    fac = _factura(_cliente_con_rfc(), autor, tasa=iva)

    r = ingesta_cfdi.recibir(_xml(total="1160.00"))
    assert r["ok"] and r["estado"] == ESTADO_LIGADO
    assert r["factura"] == fac.codigo

    fac.refresh_from_db()
    assert fac.cfdi_uuid.upper() == "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"


# ── Lo que NO debe pasar solo ──────────────────────────────────────────────


def test_dos_candidatas_quedan_pendientes(usuario_factory, iva):
    """Adivinar dejaría la contabilidad apoyada en una suposición que nadie
    revisó. Es peor que no ligar."""
    from apps.facturacion import ingesta_cfdi
    from apps.facturacion.models import ESTADO_PENDIENTE

    autor = usuario_factory(rol="super_admin")
    cli = _cliente_con_rfc()
    a = _factura(cli, autor, tasa=iva)
    b = _factura(cli, autor, tasa=iva)

    r = ingesta_cfdi.recibir(_xml(total="1160.00"))
    assert r["estado"] == ESTADO_PENDIENTE
    assert "2 facturas" in r["mensaje"]
    assert a.codigo in r["mensaje"] and b.codigo in r["mensaje"]

    a.refresh_from_db()
    b.refresh_from_db()
    assert a.cfdi_uuid == "" and b.cfdi_uuid == "", "se ligó a ciegas"


def test_sin_candidata_queda_pendiente_con_el_motivo(usuario_factory, iva):
    from apps.facturacion import ingesta_cfdi
    from apps.facturacion.models import ESTADO_PENDIENTE

    autor = usuario_factory(rol="super_admin")
    _factura(_cliente_con_rfc(), autor, precio="500.00", tasa=iva)

    r = ingesta_cfdi.recibir(_xml(total="99999.00"))
    assert r["estado"] == ESTADO_PENDIENTE
    assert "No se encontró" in r["mensaje"]


def test_una_factura_que_ya_tiene_comprobante_no_es_candidata(usuario_factory, iva):
    """Si ya tiene el suyo, el que llega es de otra."""
    from apps.facturacion import ingesta_cfdi
    from apps.facturacion.models import ESTADO_PENDIENTE

    autor = usuario_factory(rol="super_admin")
    fac = _factura(_cliente_con_rfc(), autor, tasa=iva)
    fac.cfdi_uuid = "OTRO-UUID-YA-PUESTO"
    fac.save(update_fields=["cfdi_uuid"])

    r = ingesta_cfdi.recibir(_xml(total="1160.00"))
    assert r["estado"] == ESTADO_PENDIENTE


def test_la_factura_de_un_proveedor_no_se_cuela_como_ingreso(usuario_factory, iva):
    """Nos la emitieron a NOSOTROS: es un gasto. Ligarla a una Factura —que es
    lo que le cobramos a un cliente— metería una compra en los ingresos."""
    from apps.facturacion import ingesta_cfdi
    from apps.facturacion.models import ESTADO_PENDIENTE

    autor = usuario_factory(rol="super_admin")
    fac = _factura(_cliente_con_rfc(), autor, tasa=iva)

    # Emisor: el proveedor. Receptor: nosotros.
    r = ingesta_cfdi.recibir(_xml(emisor="SCP930101ABC", receptor=RFC_NUESTRO))
    assert r["estado"] == ESTADO_PENDIENTE
    assert "nos emitió" in r["mensaje"]

    fac.refresh_from_db()
    assert fac.cfdi_uuid == ""


# ── Que no se duplique ─────────────────────────────────────────────────────


def test_el_mismo_correo_reenviado_no_archiva_dos_veces(usuario_factory, iva):
    """El folio fiscal es único en todo México: es lo que lo garantiza."""
    from apps.facturacion import ingesta_cfdi
    from apps.facturacion.models import CfdiEntrante

    autor = usuario_factory(rol="super_admin")
    _factura(_cliente_con_rfc(), autor, tasa=iva)

    ingesta_cfdi.recibir(_xml())
    r2 = ingesta_cfdi.recibir(_xml())

    assert r2["ok"] is True
    assert "Ya se había recibido" in r2["mensaje"]
    assert CfdiEntrante.objects.filter(uuid__iexact="a1b2c3d4-e5f6-7890-abcd-ef1234567890").count() == 1


# ── Basura que llega al buzón ──────────────────────────────────────────────


def test_un_adjunto_que_no_es_cfdi_se_rechaza_sin_registrar():
    from apps.facturacion import ingesta_cfdi
    from apps.facturacion.models import CfdiEntrante

    r = ingesta_cfdi.recibir(b"esto es la firma de un correo")
    assert r["ok"] is False
    assert r["estado"] == "rechazado"
    assert CfdiEntrante.objects.count() == 0


def test_un_comprobante_sin_timbrar_no_se_archiva():
    """Sin folio fiscal el SAT no lo reconoce: archivarlo dejaría la
    contabilidad apoyada en un papel que no vale."""
    from apps.facturacion import ingesta_cfdi

    sin_timbre = _xml().replace(
        b'<tfd:TimbreFiscalDigital UUID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"/>', b"")
    r = ingesta_cfdi.recibir(sin_timbre)
    assert r["ok"] is False


def test_una_bomba_de_expansion_se_rechaza():
    """El buzón lo puede escribir cualquiera."""
    from apps.facturacion import ingesta_cfdi

    bomba = (b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "AA"><!ENTITY b "&a;&a;">]>'
             b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4">&b;</cfdi:Comprobante>')
    r = ingesta_cfdi.recibir(bomba)
    assert r["ok"] is False
