"""Cerrar el flujo de los CFDI recibidos (S-Pendientes-Sep28, Deploy 2).

Dos huecos que dejó S-NUC-Servicios:

1. **No había cómo resolver un pendiente.** Lo dudoso quedaba en
   `CfdiEntrante` con su motivo, y la única pantalla (en La Gerencia) sólo
   sabía ignorarlo.
2. **Los CFDI de proveedor no generaban su egreso.** El gasto existía en papel
   y no en Tesorería.

Lo que estas pruebas cuidan, en orden de lo que dolería:

- **Que un gasto no se cuente dos veces.** Si ya hay un egreso que casa con el
  comprobante (mismo proveedor, monto ±$1, fecha ±15 días, sin CFDI), se
  ofrece ligarlo; el Chalán no crea otro sin que se lo pidan; y un comprobante
  no puede respaldar dos egresos (lo garantiza la base: es uno a uno).
- **Que nada se cree solo.** El egreso nace del formulario de siempre,
  prellenado, y lo guarda una persona.
- **Que el XML de verdad se guarde.** Antes la llamada tronaba con TypeError
  en cada CFDI y el `except` se lo tragaba: el archivo nunca llegaba al disco.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

RFC_NUESTRO = "LCE240101XYZ"
RFC_PROVEEDOR = "SCP930101ABC"
RFC_CLIENTE = "OPT150505AB1"
UUID_PROV = "11111111-2222-3333-4444-555555555555"


def _xml_proveedor(*, uuid=UUID_PROV, total="1160.00", subtotal="1000.00", iva="160.00",
                   emisor=RFC_PROVEEDOR, receptor=RFC_NUESTRO, fecha="2026-09-20T10:00:00",
                   descuento=None, retenciones=None) -> bytes:
    desc = f' Descuento="{descuento}"' if descuento else ""
    ret = ""
    if retenciones:
        ret = (f' TotalImpuestosRetenidos="{retenciones}"')
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  Version="4.0" Serie="A" Folio="1234" Fecha="{fecha}"
  SubTotal="{subtotal}"{desc} Total="{total}" Moneda="MXN" TipoDeComprobante="I">
  <cfdi:Emisor Rfc="{emisor}" Nombre="SIMIL CUERO PLYMOUTH SA DE CV"/>
  <cfdi:Receptor Rfc="{receptor}" Nombre="LEARNING CENTER"/>
  <cfdi:Conceptos>
    <cfdi:Concepto Descripcion="Vinil textil negro 50m" Cantidad="2">
      <cfdi:Impuestos>
        <cfdi:Traslados><cfdi:Traslado Impuesto="002" Importe="{iva}"/></cfdi:Traslados>
      </cfdi:Impuestos>
    </cfdi:Concepto>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="{iva}"{ret}>
    <cfdi:Traslados><cfdi:Traslado Impuesto="002" TasaOCuota="0.160000" Importe="{iva}"/></cfdi:Traslados>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="{uuid}"/>
  </cfdi:Complemento>
</cfdi:Comprobante>""".encode()


@pytest.fixture(autouse=True)
def _somos_nosotros(monkeypatch):
    from apps.facturacion import ingesta_cfdi

    monkeypatch.setattr(ingesta_cfdi, "_rfc_propio", lambda: RFC_NUESTRO)


@pytest.fixture
def admin(usuario_factory):
    return usuario_factory(rol="super_admin")


@pytest.fixture
def proveedor(db):
    from apps.el_catalogo.models import Proveedor

    return Proveedor.objects.create(razon_social="Simil Cuero Plymouth", rfc=RFC_PROVEEDOR)


@pytest.fixture
def centro(db):
    from apps.tesoreria.models import CentroDeCosto

    return CentroDeCosto.objects.get(slug="insumos-de-proyecto")


def _recibir(xml: bytes, pdf: bytes | None = None):
    from apps.facturacion import ingesta_cfdi
    from apps.facturacion.models import CfdiEntrante

    r = ingesta_cfdi.recibir(xml, nombre="cfdi.xml", pdf=pdf)
    assert r["ok"], r
    return CfdiEntrante.objects.get(uuid=r["uuid"])


def _egreso(proveedor, centro, autor, **kw):
    from apps.tesoreria.models import Egreso

    datos = {"monto": Decimal("1160.00"), "fecha": date(2026, 9, 18),
             "descripcion": "Vinil (capturado a mano)", "centro_de_costo": centro,
             "proveedor": proveedor, "proveedor_nombre": proveedor.razon_social,
             "creado_por": autor}
    datos.update(kw)
    return Egreso.objects.create(**datos)


# ── Leer el comprobante completo ───────────────────────────────────────────


def test_lee_el_iva_del_comprobante_sin_contarlo_dos_veces():
    """El nodo Impuestos aparece dentro de cada concepto Y en la raíz con los
    totales. Sumar los dos daría el IVA doble."""
    from lib import cfdi

    lec = cfdi.leer(_xml_proveedor())
    assert lec.iva == Decimal("160.00")
    assert lec.base == Decimal("1000.00")
    assert lec.tipo_comprobante == "I"


def test_la_base_descuenta_el_descuento():
    from lib import cfdi

    lec = cfdi.leer(_xml_proveedor(subtotal="1100.00", descuento="100.00"))
    assert lec.base == Decimal("1000.00")


def test_la_defensa_contra_entidades_sigue_en_pie():
    """El XML viene de un buzón al que cualquiera escribe."""
    from lib import cfdi

    bomba = (b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "AA">]>'
             b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4">&a;</cfdi:Comprobante>')
    assert cfdi.leer(bomba).ok is False


# ── La ingesta ─────────────────────────────────────────────────────────────


def test_la_ingesta_guarda_el_desglose_y_reconoce_al_proveedor(proveedor):
    c = _recibir(_xml_proveedor())
    assert c.subtotal == Decimal("1000.00") and c.iva == Decimal("160.00")
    assert c.proveedor == proveedor, "el RFC del emisor casa con UN proveedor"
    assert "Vinil" in c.concepto


def test_con_dos_proveedores_del_mismo_rfc_no_se_adivina(proveedor):
    from apps.el_catalogo.models import Proveedor

    Proveedor.objects.create(razon_social="Otro con el mismo RFC", rfc=RFC_PROVEEDOR)
    c = _recibir(_xml_proveedor())
    assert c.proveedor_id is None


def test_el_xml_de_verdad_se_guarda_en_el_almacen():
    """El bug: `subir()` recibía bytes con `nombre=` y `mime=` que no acepta,
    tronaba con TypeError en CADA comprobante y el `except` se lo tragaba. El
    XML nunca llegaba al disco y no había con qué respaldar un gasto."""
    from lib import almacen

    c = _recibir(_xml_proveedor())
    assert c.archivo_id, "el XML no se guardó"
    contenido, mime, _ = almacen.leer(c.archivo_id)
    assert UUID_PROV.encode() in contenido


def test_reenviar_un_cfdi_viejo_recupera_su_archivo_sin_duplicarlo():
    """Los que entraron con el bug no tienen XML guardado. Reenviar el correo
    no debe crear otro registro —el folio fiscal es único— pero sí completar
    lo que le falta: su archivo, su PDF y su desglose."""
    from apps.facturacion import ingesta_cfdi
    from apps.facturacion.models import CfdiEntrante

    viejo = CfdiEntrante.objects.create(
        uuid=UUID_PROV, emisor_rfc=RFC_PROVEEDOR, receptor_rfc=RFC_NUESTRO,
        total=Decimal("1160.00"), archivo_id="")
    r = ingesta_cfdi.recibir(_xml_proveedor(), nombre="cfdi.xml", pdf=b"%PDF-1.4 x")
    assert r["ok"] and CfdiEntrante.objects.count() == 1
    viejo.refresh_from_db()
    assert viejo.archivo_id and viejo.pdf_id
    assert viejo.iva == Decimal("160.00") and viejo.subtotal == Decimal("1000.00")
    assert "faltaba" in r["mensaje"]

    # Una vez completo, reenviarlo ya no toca nada.
    r2 = ingesta_cfdi.recibir(_xml_proveedor(), nombre="cfdi.xml")
    assert "faltaba" not in r2["mensaje"]


def test_el_pdf_que_llega_con_el_correo_se_guarda():
    c = _recibir(_xml_proveedor(), pdf=b"%PDF-1.4 un pdf de prueba")
    assert c.pdf_id
    assert c.comprobante_id == c.pdf_id, "el comprobante del gasto es el PDF si llegó"


def test_lo_que_no_es_pdf_no_se_guarda_como_pdf():
    c = _recibir(_xml_proveedor(), pdf=b"<html>esto no es un pdf</html>")
    assert c.pdf_id == ""


def test_el_endpoint_acepta_el_pdf_en_el_mismo_envio(client, monkeypatch):
    from apps.facturacion import views_ingesta
    from apps.facturacion.models import CfdiEntrante
    from django.core.files.uploadedfile import SimpleUploadedFile

    monkeypatch.setattr(views_ingesta, "_tokens", lambda: ["tok-largo"])
    r = client.post(
        reverse("facturacion:cfdi-entrante"),
        {"archivo": SimpleUploadedFile("f.xml", _xml_proveedor(), content_type="application/xml"),
         "pdf": SimpleUploadedFile("f.pdf", b"%PDF-1.4 x", content_type="application/pdf")},
        headers={"x-cfdi-token": "tok-largo"},
    )
    assert r.status_code == 200, r.content
    assert CfdiEntrante.objects.get(uuid=UUID_PROV).pdf_id


# ── Clasificar y casar ─────────────────────────────────────────────────────


def test_clasifica_proveedor_propio_y_dudoso():
    from apps.facturacion import cfdi_recibidos as svc
    from apps.facturacion.models import CfdiEntrante

    prov = CfdiEntrante(uuid="a", emisor_rfc=RFC_PROVEEDOR, receptor_rfc=RFC_NUESTRO)
    nuestro = CfdiEntrante(uuid="b", emisor_rfc=RFC_NUESTRO, receptor_rfc=RFC_CLIENTE)
    raro = CfdiEntrante(uuid="c", emisor_rfc="XXX", receptor_rfc="YYY")
    assert svc.clasificar(prov, RFC_NUESTRO) == svc.TIPO_PROVEEDOR
    assert svc.clasificar(nuestro, RFC_NUESTRO) == svc.TIPO_PROPIO
    assert svc.clasificar(raro, RFC_NUESTRO) == svc.TIPO_DUDOSO


def test_sin_rfc_propio_el_catalogo_decide(proveedor):
    """Hay pendientes de antes de configurar el RFC del despacho."""
    from apps.facturacion import cfdi_recibidos as svc
    from apps.facturacion.models import CfdiEntrante

    c = CfdiEntrante(uuid="a", emisor_rfc=RFC_PROVEEDOR, receptor_rfc="ALGO")
    assert svc.clasificar(c, "") == svc.TIPO_PROVEEDOR


def test_egresos_que_casan_respeta_proveedor_monto_fecha_y_cfdi(proveedor, centro, admin):
    from apps.el_catalogo.models import Proveedor
    from apps.facturacion import cfdi_recibidos as svc

    c = _recibir(_xml_proveedor(total="1160.00", fecha="2026-09-20T10:00:00"))
    si = _egreso(proveedor, centro, admin, monto=Decimal("1159.50"), fecha=date(2026, 9, 10))
    # Lo que NO debe casar:
    _egreso(proveedor, centro, admin, monto=Decimal("1300.00"))                    # otro monto
    _egreso(proveedor, centro, admin, fecha=date(2026, 8, 1))                       # fuera de la ventana
    _egreso(proveedor, centro, admin, anulado=True)                                  # anulado
    otro = Proveedor.objects.create(razon_social="Otro Proveedor")
    _egreso(otro, centro, admin)                                                     # otro proveedor
    ya_respaldado = _egreso(proveedor, centro, admin, fecha=date(2026, 9, 19))      # ya tiene su CFDI
    otro_cfdi = _recibir(_xml_proveedor(uuid="CCCCCCCC-1111-2222-3333-444444444444"))
    svc.ligar_egreso(otro_cfdi, ya_respaldado, admin)

    assert [e.pk for e in svc.egresos_que_casan(c)] == [si.pk]


def test_sin_proveedor_conocido_no_se_ofrece_ningun_egreso(centro, admin):
    """Comparar sólo por monto ligaría el gasto de un proveedor al comprobante
    de otro."""
    from apps.facturacion import cfdi_recibidos as svc

    c = _recibir(_xml_proveedor())
    assert c.proveedor_id is None
    assert svc.egresos_que_casan(c) == []


# ── Ligar ──────────────────────────────────────────────────────────────────


def test_ligar_a_un_egreso_lo_resuelve_y_le_pone_el_comprobante(proveedor, centro, admin):
    from apps.facturacion import cfdi_recibidos as svc
    from apps.facturacion.models import ESTADO_LIGADO

    c = _recibir(_xml_proveedor(), pdf=b"%PDF-1.4 x")
    eg = _egreso(proveedor, centro, admin)
    svc.ligar_egreso(c, eg, admin)

    c.refresh_from_db()
    eg.refresh_from_db()
    assert c.estado == ESTADO_LIGADO and c.egreso_id == eg.pk
    assert eg.tiene_comprobante and eg.drive_file_id == c.pdf_id


def test_un_egreso_no_queda_respaldado_por_dos_comprobantes(proveedor, centro, admin):
    from apps.facturacion import cfdi_recibidos as svc

    a = _recibir(_xml_proveedor(uuid="AAAAAAAA-1111-2222-3333-444444444444"))
    b = _recibir(_xml_proveedor(uuid="BBBBBBBB-1111-2222-3333-444444444444"))
    eg = _egreso(proveedor, centro, admin)
    svc.ligar_egreso(a, eg, admin)
    with pytest.raises(svc.CfdiNoResoluble):
        svc.ligar_egreso(b, eg, admin)


def test_ligar_a_factura_guarda_el_folio_fiscal_en_la_factura(admin):
    from apps.facturacion import cfdi_recibidos as svc
    from apps.facturacion.models import Factura
    from apps.la_cartera.models import Cliente

    cli = Cliente.objects.create(razon_social="Optimist", rfc=RFC_CLIENTE, activo=True)
    fac = Factura.objects.create(cliente=cli, titulo="F", creado_por=admin)
    c = _recibir(_xml_proveedor(emisor=RFC_NUESTRO, receptor=RFC_CLIENTE))  # nuestra, sin candidata
    svc.ligar_factura(c, fac, admin)
    fac.refresh_from_db()
    assert fac.cfdi_uuid.upper() == c.uuid
    assert fac.xml_file_id, "el XML quedó en la factura"


# ── La pantalla de Tesorería ───────────────────────────────────────────────


def test_la_pantalla_ofrece_ligar_el_egreso_que_ya_existe(client, admin, proveedor, centro):
    c = _recibir(_xml_proveedor())
    eg = _egreso(proveedor, centro, admin)
    client.force_login(admin)
    r = client.get(reverse("tesoreria:cfdi-recibidos"))
    assert r.status_code == 200
    html = r.content.decode()
    assert f"Ligar a {eg.codigo}" in html
    assert f"?cfdi={c.pk}" in html, "falta el botón de crear egreso"
    assert "O crear un egreso nuevo" in html, "con un egreso que casa, crear es la opción secundaria"


def test_la_pantalla_de_los_ya_ligados_dice_a_que_egreso(client, admin, proveedor, centro):
    """Los filtros «Ligados» y «Todos» pintan la otra rama de la tarjeta."""
    from apps.facturacion import cfdi_recibidos as svc

    c = _recibir(_xml_proveedor())
    eg = _egreso(proveedor, centro, admin)
    svc.ligar_egreso(c, eg, admin)
    client.force_login(admin)
    for filtro in ("ligado", "todos"):
        r = client.get(reverse("tesoreria:cfdi-recibidos") + f"?estado={filtro}")
        assert r.status_code == 200
        html = r.content.decode()
        assert "Respalda el egreso" in html and eg.codigo in html, filtro
        assert f"?cfdi={c.pk}" not in html, "un ligado ya no ofrece crear otro egreso"


def test_sin_permiso_de_tesoreria_no_se_entra(client, usuario_factory):
    client.force_login(usuario_factory(rol="disenador"))
    assert client.get(reverse("tesoreria:cfdi-recibidos")).status_code == 403


def test_ver_no_alcanza_para_resolver(client, usuario_factory, proveedor, centro, admin):
    """Cada acción pide SU permiso granular (§4 #20): ver Tesorería no es capturar egresos."""
    from cuentas.models.permiso_usuario import PermisoUsuario

    u = usuario_factory(rol="miembro")
    PermisoUsuario.objects.create(usuario=u, modulo="tesoreria", permiso="ver")
    c = _recibir(_xml_proveedor())
    eg = _egreso(proveedor, centro, admin)
    client.force_login(u)
    assert client.get(reverse("tesoreria:cfdi-recibidos")).status_code == 200
    r = client.post(reverse("tesoreria:cfdi-accion", args=[c.pk]),
                    {"accion": "ligar_egreso", "egreso": eg.pk})
    assert r.status_code == 403
    c.refresh_from_db()
    assert c.egreso_id is None


def test_asignar_proveedor_desde_la_pantalla_aprende_su_rfc(client, admin):
    from apps.el_catalogo.models import Proveedor

    sin_rfc = Proveedor.objects.create(razon_social="Simil Cuero Plymouth")
    c = _recibir(_xml_proveedor())
    client.force_login(admin)
    r = client.post(reverse("tesoreria:cfdi-accion", args=[c.pk]),
                    {"accion": "proveedor", "proveedor": sin_rfc.pk})
    assert r.status_code == 302
    c.refresh_from_db()
    sin_rfc.refresh_from_db()
    assert c.proveedor_id == sin_rfc.pk
    assert sin_rfc.rfc == RFC_PROVEEDOR, "el siguiente CFDI de este proveedor se reconoce solo"


def test_ignorar_desde_la_pantalla(client, admin):
    from apps.facturacion.models import ESTADO_IGNORADO

    c = _recibir(_xml_proveedor())
    client.force_login(admin)
    client.post(reverse("tesoreria:cfdi-accion", args=[c.pk]),
                {"accion": "ignorar", "motivo": "correo duplicado"})
    c.refresh_from_db()
    assert c.estado == ESTADO_IGNORADO and "duplicado" in c.motivo


def test_el_xml_se_descarga_no_se_interpreta(client, admin):
    c = _recibir(_xml_proveedor())
    client.force_login(admin)
    r = client.get(reverse("tesoreria:cfdi-archivo", args=[c.pk]) + "?cual=xml")
    assert r.status_code == 200
    assert r["Content-Disposition"].startswith("attachment")
    assert r["X-Content-Type-Options"] == "nosniff"


# ── El modal de «Nuevo egreso», prellenado ─────────────────────────────────


def test_el_modal_se_abre_prellenado_con_el_cfdi(client, admin, proveedor):
    c = _recibir(_xml_proveedor())
    client.force_login(admin)
    r = client.get(reverse("tesoreria:egreso-nuevo") + f"?cfdi={c.pk}",
                   headers={"HX-Request": "true"})
    assert r.status_code == 200
    html = r.content.decode()
    assert f'name="cfdi_entrante" value="{c.pk}"' in html
    assert "Datos leídos del CFDI" in html
    form = r.context["form"]
    assert form.initial["subtotal"] == Decimal("1160.00"), "se captura el TOTAL con IVA"
    assert form.initial["proveedor"] == proveedor.pk
    assert form.initial["fecha"] == date(2026, 9, 20)


def test_la_pagina_completa_del_egreso_tambien_se_prellena(client, admin, proveedor):
    """Sin HTMX (abrir el enlace en otra pestaña) sale la página completa."""
    c = _recibir(_xml_proveedor())
    client.force_login(admin)
    r = client.get(reverse("tesoreria:egreso-nuevo") + f"?cfdi={c.pk}")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Datos leídos del CFDI" in html and f'name="cfdi_entrante" value="{c.pk}"' in html


def test_la_pantalla_de_los_ignorados_abre(client, admin):
    from apps.facturacion import cfdi_recibidos as svc

    c = _recibir(_xml_proveedor())
    svc.ignorar(c, admin, "prueba")
    client.force_login(admin)
    r = client.get(reverse("tesoreria:cfdi-recibidos") + "?estado=ignorado")
    assert r.status_code == 200
    assert f'id="cfdi-{c.pk}"' in r.content.decode()


def test_sin_proveedor_el_alta_rapida_trae_nombre_y_rfc(client, admin):
    c = _recibir(_xml_proveedor())
    client.force_login(admin)
    r = client.get(reverse("tesoreria:egreso-nuevo") + f"?cfdi={c.pk}",
                   headers={"HX-Request": "true"})
    html = r.content.decode()
    assert f'value="{RFC_PROVEEDOR}"' in html
    assert "<details class=\"mt-2 text-sm\" open>" in html


def _post_egreso(client, c, proveedor, centro, total="1160.00"):
    return client.post(reverse("tesoreria:egreso-nuevo"), {
        "cfdi_entrante": c.pk, "fecha": "2026-09-20", "subtotal": total,
        "incluye_iva": "on", "descripcion": "Vinil textil", "proveedor": proveedor.pk,
        "centro_de_costo": centro.pk, "estado_pago": "pagado", "metodo": "tarjeta_empresa",
        "next": reverse("tesoreria:cfdi-recibidos"),
    }, headers={"HX-Request": "true"})


def test_guardar_el_modal_crea_el_egreso_y_lo_liga(client, admin, proveedor, centro):
    from apps.tesoreria.models import Egreso

    c = _recibir(_xml_proveedor(subtotal="1100.00", descuento="100.00"))
    client.force_login(admin)
    r = _post_egreso(client, c, proveedor, centro)
    assert r.status_code == 204, getattr(r, "context", None) and r.context["form"].errors
    eg = Egreso.objects.get()
    c.refresh_from_db()
    assert c.egreso_id == eg.pk
    assert eg.origen == "cfdi"
    assert eg.monto == Decimal("1160.00")
    assert eg.subtotal == Decimal("1000.00"), "la base sale del CFDI, no de ÷1.16"
    assert eg.tiene_comprobante


def test_con_retenciones_la_base_sale_del_cfdi_y_no_de_dividir(client, admin, proveedor, centro):
    """Con descuento a secas, total ÷ 1.16 da la misma base por casualidad. Con
    retenciones (honorarios) no: 1,053.33 ÷ 1.16 = 908.04, y la base real es
    1,000. Si se dividiera, el gasto quedaría subestimado en la contabilidad."""
    from apps.tesoreria.models import Egreso

    c = _recibir(_xml_proveedor(total="1053.33", subtotal="1000.00", iva="160.00",
                                retenciones="106.67"))
    assert c.retenciones == Decimal("106.67")
    client.force_login(admin)
    r = _post_egreso(client, c, proveedor, centro, total="1053.33")
    assert r.status_code == 204, getattr(r, "context", None) and r.context["form"].errors
    eg = Egreso.objects.get()
    assert eg.monto == Decimal("1053.33")
    assert eg.subtotal == Decimal("1000.00")


def test_el_mismo_cfdi_no_genera_dos_egresos(client, admin, proveedor, centro):
    """Dos personas —o un doble clic— guardando el mismo comprobante."""
    from apps.tesoreria.models import Egreso

    c = _recibir(_xml_proveedor())
    client.force_login(admin)
    _post_egreso(client, c, proveedor, centro)
    r = _post_egreso(client, c, proveedor, centro)
    assert r.status_code == 200, "el segundo intento debía volver con el error"
    assert "ya respalda" in r.content.decode()
    assert Egreso.objects.count() == 1


def test_el_modal_con_cfdi_pide_permiso_de_capturar_egresos(client, usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario

    u = usuario_factory(rol="contador")
    PermisoUsuario.objects.update_or_create(
        usuario=u, modulo="tesoreria", permiso="capturar_egreso", defaults={"activo": False})
    c = _recibir(_xml_proveedor())
    client.force_login(u)
    r = client.get(reverse("tesoreria:egreso-nuevo") + f"?cfdi={c.pk}",
                   headers={"HX-Request": "true"})
    assert r.status_code == 403


def test_nuevo_egreso_exige_sesion(client):
    """El decorador se había quedado pegado a un helper (Fase C3, junio): sin
    sesión respondía el 403 del gate en vez de mandar a iniciar sesión."""
    from django.conf import settings

    r = client.get(reverse("tesoreria:egreso-nuevo"))
    assert r.status_code == 302
    assert r["Location"].startswith(str(settings.LOGIN_URL)), r["Location"]


def test_el_detalle_del_egreso_muestra_su_cfdi(client, admin, proveedor, centro):
    from apps.facturacion import cfdi_recibidos as svc

    c = _recibir(_xml_proveedor())
    eg = _egreso(proveedor, centro, admin)
    svc.ligar_egreso(c, eg, admin)
    client.force_login(admin)
    html = client.get(reverse("tesoreria:egreso-detalle", args=[eg.pk])).content.decode()
    assert "CFDI del proveedor" in html and c.uuid in html


# ── El Chalán ──────────────────────────────────────────────────────────────


def _accion(tipo, payload):
    from types import SimpleNamespace

    return SimpleNamespace(tipo=tipo, payload=payload, entidad_tipo="", entidad_id=None)


def test_el_chalan_registra_el_egreso_de_un_cfdi(admin, proveedor, centro):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.tesoreria.models import Egreso

    c = _recibir(_xml_proveedor())
    acc = _accion("registrar_egreso_desde_cfdi", {"cfdi": c.uuid, "centro_de_costo_slug": centro.slug})
    EJECUTORES["registrar_egreso_desde_cfdi"](acc, admin, {})
    eg = Egreso.objects.get(pk=acc.entidad_id)
    assert eg.monto == Decimal("1160.00") and eg.proveedor == proveedor and eg.origen == "cfdi"
    c.refresh_from_db()
    assert c.egreso_id == eg.pk


def test_el_chalan_no_duplica_un_gasto_que_ya_existe(admin, proveedor, centro):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.tesoreria.models import Egreso

    c = _recibir(_xml_proveedor())
    existente = _egreso(proveedor, centro, admin)
    with pytest.raises(ValueError, match=existente.codigo):
        EJECUTORES["registrar_egreso_desde_cfdi"](_accion("registrar_egreso_desde_cfdi", {"cfdi": c.uuid}), admin, {})
    assert Egreso.objects.count() == 1

    # Ligarlo sí.
    acc = _accion("registrar_egreso_desde_cfdi", {"cfdi": c.uuid, "egreso_codigo": existente.codigo})
    EJECUTORES["registrar_egreso_desde_cfdi"](acc, admin, {})
    c.refresh_from_db()
    assert c.egreso_id == existente.pk and Egreso.objects.count() == 1


def test_el_chalan_no_trata_una_factura_nuestra_como_gasto(admin):
    from apps.el_dictado.ejecutores import EJECUTORES

    c = _recibir(_xml_proveedor(emisor=RFC_NUESTRO, receptor=RFC_CLIENTE))
    with pytest.raises(ValueError, match="NUESTRA"):
        EJECUTORES["registrar_egreso_desde_cfdi"](_accion("registrar_egreso_desde_cfdi", {"cfdi": c.uuid}), admin, {})


def test_el_chalan_liga_un_cfdi_nuestro_por_folio(admin):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.facturacion.models import Factura
    from apps.la_cartera.models import Cliente

    cli = Cliente.objects.create(razon_social="Optimist", rfc=RFC_CLIENTE, activo=True)
    fac = Factura.objects.create(cliente=cli, titulo="F", creado_por=admin)
    c = _recibir(_xml_proveedor(emisor=RFC_NUESTRO, receptor=RFC_CLIENTE))
    acc = _accion("ligar_cfdi_a_factura", {"cfdi": c.uuid, "factura_codigo": f"F-{fac.folio_numero}"})
    EJECUTORES["ligar_cfdi_a_factura"](acc, admin, {})
    fac.refresh_from_db()
    assert fac.cfdi_uuid.upper() == c.uuid


def test_el_chalan_sin_permiso_de_finanzas_no_registra(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    c = _recibir(_xml_proveedor())
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["registrar_egreso_desde_cfdi"](
            _accion("registrar_egreso_desde_cfdi", {"cfdi": c.uuid}), usuario_factory(rol="disenador"), {})


def test_el_chalan_respeta_el_permiso_de_capturar_egresos(usuario_factory, proveedor, centro):
    """Ver finanzas no alcanza: si a alguien le quitaron «capturar egresos»,
    la pantalla le dice que no y el Chalán también (§4 #20)."""
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.tesoreria.models import Egreso

    from cuentas.models.permiso_usuario import PermisoUsuario

    u = usuario_factory(rol="contador")
    PermisoUsuario.objects.update_or_create(
        usuario=u, modulo="tesoreria", permiso="capturar_egreso", defaults={"activo": False})
    c = _recibir(_xml_proveedor())
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["registrar_egreso_desde_cfdi"](
            _accion("registrar_egreso_desde_cfdi",
                    {"cfdi": c.uuid, "centro_de_costo_slug": centro.slug}), u, {})
    assert Egreso.objects.count() == 0


def test_la_capacidad_cfdi_pendientes_se_llama_como_el_registro(admin, proveedor, centro):
    """El registro despacha `fn(args, usuario)`; y la lectura trae lo que el
    Chalán necesita para no duplicar: el egreso que ya casa."""
    import capacidades.lecturas  # noqa: F401 — importar es lo que registra
    from capacidades.gating import gate_ok
    from capacidades.registro import CAPACIDADES

    c = _recibir(_xml_proveedor())
    eg = _egreso(proveedor, centro, admin)
    cap = CAPACIDADES["cfdi_pendientes"]
    assert cap.gating == "finanzas" and gate_ok(cap.gating, admin)
    r = cap.fn({}, admin)
    assert r["total"] == 1 and r["por_tipo"]["de_proveedor"] == 1
    fila = r["pendientes"][0]
    assert fila["uuid"] == c.uuid and fila["egresos_que_casan"] == [eg.codigo]


def test_las_acciones_nuevas_estan_en_los_tres_lugares():
    from pathlib import Path

    from apps.el_dictado.ejecutores import EJECUTORES

    from lib.dictado_catalogo import COMANDOS_DICTADO, CONSULTAS_CHAT, _gating_checks

    raiz = Path(__file__).resolve().parent.parent.parent
    prompt = (raiz / "el-taller/apps/el_dictado/prompt.py").read_text()
    catalogo = {c["tipo"]: c for c in COMANDOS_DICTADO}
    for tipo in ("registrar_egreso_desde_cfdi", "ligar_cfdi_a_factura"):
        assert tipo in EJECUTORES, f"{tipo}: falta el ejecutor"
        assert tipo in catalogo, f"{tipo}: falta en el catálogo"
        assert tipo in prompt, f"{tipo}: falta en el prompt"
        assert catalogo[tipo]["gating"] in _gating_checks(), f"{tipo}: gating inexistente"
    assert any("cfdi_pendientes" in c["nombre"] for c in CONSULTAS_CHAT)


def test_la_tesoreria_avisa_cuando_hay_cfdi_esperando(client, admin):
    _recibir(_xml_proveedor())
    client.force_login(admin)
    html = client.get(reverse("tesoreria:landing")).content.decode()
    assert reverse("tesoreria:cfdi-recibidos") in html
    assert "espera que alguien decida" in html


def test_fecha_fuera_de_ventana_no_casa(proveedor, centro, admin):
    """Quince días es la ventana: la factura llega días después de pagar."""
    from apps.facturacion import cfdi_recibidos as svc

    c = _recibir(_xml_proveedor(fecha="2026-09-20T10:00:00"))
    _egreso(proveedor, centro, admin, fecha=date(2026, 9, 20) - timedelta(days=svc.DIAS_VENTANA + 1))
    assert svc.egresos_que_casan(c) == []


# ── Ignorar pide el permiso del lado al que pertenece (deuda Sep28) ────────
# Ligar un CFDI PROPIO pide `facturacion.editar`; ignorarlo pedía
# `tesoreria.capturar_egreso`, así que quien llevaba la facturación no podía
# descartar un duplicado de su propia factura, y quien capturaba gastos sí.

UUID_PROPIO = "99999999-8888-7777-6666-555555555555"
UUID_RARO = "77777777-6666-5555-4444-333333333333"


def _con_permisos(usuario_factory, *pares):
    from cuentas.models.permiso_usuario import PermisoUsuario

    u = usuario_factory(rol="miembro")
    for modulo, permiso in (("tesoreria", "ver"), *pares):
        PermisoUsuario.objects.create(usuario=u, modulo=modulo, permiso=permiso)
    return u


def _ignorar(client, c):
    return client.post(reverse("tesoreria:cfdi-accion", args=[c.pk]),
                       {"accion": "ignorar", "motivo": "duplicado"})


def _propio():
    return _recibir(_xml_proveedor(uuid=UUID_PROPIO, emisor=RFC_NUESTRO, receptor=RFC_CLIENTE))


def _dudoso():
    """Ni nos lo emitieron ni lo emitimos, y nadie en el catálogo tiene esos RFC.
    Se crea directo: la ingesta ya lo habría explicado en `motivo`."""
    from apps.facturacion.models import CfdiEntrante

    return CfdiEntrante.objects.create(uuid=UUID_RARO, emisor_rfc="XAXX010101000",
                                       receptor_rfc="XEXX010101000")


@pytest.mark.parametrize("pares,puede", [
    ((("facturacion", "editar"),), True),
    ((("tesoreria", "capturar_egreso"),), False),
])
def test_un_cfdi_propio_se_ignora_con_permiso_de_facturacion(client, usuario_factory,
                                                             pares, puede):
    from apps.facturacion import cfdi_recibidos as svc
    from apps.facturacion.models import ESTADO_IGNORADO, ESTADO_PENDIENTE

    c = _propio()
    assert svc.clasificar(c) == svc.TIPO_PROPIO and c.estado == ESTADO_PENDIENTE
    client.force_login(_con_permisos(usuario_factory, *pares))
    r = _ignorar(client, c)
    c.refresh_from_db()
    if puede:
        assert r.status_code == 302 and c.estado == ESTADO_IGNORADO
    else:
        assert r.status_code == 403 and c.estado == ESTADO_PENDIENTE


@pytest.mark.parametrize("pares,puede", [
    ((("tesoreria", "capturar_egreso"),), True),
    ((("facturacion", "editar"),), False),
])
def test_un_cfdi_de_proveedor_se_sigue_ignorando_con_permiso_de_egresos(
        client, usuario_factory, pares, puede):
    from apps.facturacion.models import ESTADO_IGNORADO, ESTADO_PENDIENTE

    c = _recibir(_xml_proveedor())
    client.force_login(_con_permisos(usuario_factory, *pares))
    r = _ignorar(client, c)
    c.refresh_from_db()
    if puede:
        assert r.status_code == 302 and c.estado == ESTADO_IGNORADO
    else:
        assert r.status_code == 403 and c.estado == ESTADO_PENDIENTE


@pytest.mark.parametrize("pares", [(("facturacion", "editar"),),
                                   (("tesoreria", "capturar_egreso"),)])
def test_uno_dudoso_lo_ignora_cualquiera_de_los_dos_lados(client, usuario_factory, pares):
    from apps.facturacion import cfdi_recibidos as svc
    from apps.facturacion.models import ESTADO_IGNORADO

    c = _dudoso()
    assert svc.clasificar(c) == svc.TIPO_DUDOSO
    client.force_login(_con_permisos(usuario_factory, *pares))
    assert _ignorar(client, c).status_code == 302
    c.refresh_from_db()
    assert c.estado == ESTADO_IGNORADO


def test_la_pantalla_ofrece_ignorar_solo_donde_se_puede(client, usuario_factory):
    """Quien lleva la facturación ve «Ignorar» en el propio y no en el del
    proveedor; el botón no promete lo que el servidor va a negar."""
    propio = _propio()
    del_proveedor = _recibir(_xml_proveedor())
    client.force_login(_con_permisos(usuario_factory, ("facturacion", "editar")))
    html = client.get(reverse("tesoreria:cfdi-recibidos")).content.decode()

    def _tarjeta(c):
        ini = html.index(f'id="cfdi-{c.pk}"')
        return html[ini:html.index("</article>", ini)]

    assert 'value="ignorar"' in _tarjeta(propio)
    assert 'value="ignorar"' not in _tarjeta(del_proveedor)
