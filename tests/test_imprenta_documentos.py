"""La Imprenta · Deploy 3 (2026-09-29): los documentos nuevos.

Recibo de pago, estado de cuenta, remisión, orden de trabajo y comprobante de
reembolso. Lo que se cuida:

1. **Cada uno sale** con lo que tiene que decir.
2. **El permiso es el del módulo** del documento (finanzas, facturación, el
   proyecto): La Imprenta no abre nada que la persona no vea ya. Y el 404 no
   revela que el documento existe.
3. **El PDF sale del motor**, y sin motor se ofrece la versión imprimible.
4. **La marca por estado**: el ingreso anulado, el reembolso por pagar.
5. **El monto en letra** se escribe como en un cheque.
6. **La vista previa de La Gerencia** sólo enseña documentos reales de los
   módulos que la persona puede ver.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _sin_cache():
    from imprenta import config

    config.olvidar()
    yield
    config.olvidar()


@pytest.fixture
def jefe(usuario_factory):
    return usuario_factory(rol="super_admin")


@pytest.fixture
def cliente(cliente_factory, jefe):
    return cliente_factory(creado_por=jefe, razon_social="Heladería Sur", rfc="HSU010101AB1",
                           direccion="Av. Juárez 10, Pachuca")


@pytest.fixture
def ingreso(cliente, jefe):
    from apps.tesoreria.models import Ingreso

    return Ingreso.objects.create(monto=Decimal("1250.50"), descripcion="Anticipo vasos",
                                  fecha=dt.date.today(), metodo="transferencia",
                                  referencia_externa="SPEI-77", cliente=cliente, creado_por=jefe)


@pytest.fixture
def egreso(jefe, usuario_factory):
    from apps.tesoreria.models import CentroDeCosto, Egreso

    cc = CentroDeCosto.objects.create(slug="op", nombre="Operación")
    ana = usuario_factory(rol="disenador")
    return Egreso.objects.create(monto=Decimal("380"), descripcion="Tinta para plotter",
                                 fecha=dt.date.today(), centro_de_costo=cc, creado_por=jefe,
                                 metodo="tarjeta_personal", estado_pago="por_reembolsar",
                                 solicitado_por=ana, proveedor_nombre="Papelería Sol")


@pytest.fixture
def proyecto(proyecto_factory, cliente, jefe):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    prov = Proveedor.objects.create(razon_social="Crea Blanks", activo=True)
    srv = Servicio.objects.create(nombre="Tote Bag", precio_base="195", costo="80", categoria=cat)
    p = proyecto_factory(nombre="Feria de verano", cliente=cliente, creado_por=jefe,
                         fecha_compromiso=dt.date.today() + dt.timedelta(days=10))
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, proveedor=prov, cantidad=70, merma=3,
                                    precio_unitario=Decimal("195.00"), costo_unitario=Decimal("80.00"),
                                    incluir_en_calculo=True, nota="Tinta blanca")
    return p


@pytest.fixture
def factura(cliente, jefe):
    from apps.facturacion.models import Factura, FacturaItem

    f = Factura.objects.create(cliente=cliente, titulo="Vasos", creado_por=jefe, estado="emitida",
                               folio_numero=12,
                               fecha_vencimiento=dt.date.today() - dt.timedelta(days=5))
    FacturaItem.objects.create(factura=f, orden=0, descripcion="Vasos", cantidad=Decimal("1"),
                               unidad="pieza", precio_unitario=Decimal("1000.00"))
    return f


def _ver(client, tipo, pk):
    return client.get(reverse("imprenta:ver", args=[tipo, pk]))


# ── 1. Cada documento sale ──────────────────────────────────────────────────


def test_el_recibo_de_pago(client, jefe, ingreso):
    client.force_login(jefe)
    html = _ver(client, "recibo_pago", ingreso.pk).content.decode()
    assert "RECIBO DE PAGO" in html and ingreso.codigo in html
    assert "Heladería Sur" in html
    assert "MIL DOSCIENTOS CINCUENTA PESOS 50/100 M.N." in html
    assert "SPEI-77" in html
    assert "Bajar PDF" in html


def test_el_estado_de_cuenta(client, jefe, cliente, factura):
    from apps.facturacion.models import Factura

    Factura.objects.create(cliente=cliente, titulo="Cancelada", creado_por=jefe,
                           estado="cancelada", folio_numero=13)
    # Un borrador sin CFDI todavía no se le facturó a nadie: no se cobra.
    Factura.objects.create(cliente=cliente, titulo="Borrador", creado_por=jefe,
                           estado="borrador", folio_numero=14)
    client.force_login(jefe)
    html = _ver(client, "estado_cuenta", cliente.pk).content.decode()
    assert "ESTADO DE CUENTA" in html and "F12" in html
    assert "F13" not in html, "una factura cancelada no se le cobra a nadie"
    assert "F14" not in html, "un borrador sin CFDI no se le ha facturado"
    assert "Vencido" in html, "la F12 venció hace cinco días"


def test_la_remision_con_precios_si_se_encienden(client, jefe, proyecto):
    from imprenta.models import AjusteImprenta

    AjusteImprenta.objects.create(ambito="remision", valores={"bloque_precios": True})
    client.force_login(jefe)
    assert "$195" in _ver(client, "remision", proyecto.pk).content.decode()


def test_la_remision_sin_precios_de_fabrica(client, jefe, proyecto):
    client.force_login(jefe)
    html = _ver(client, "remision", proyecto.pk).content.decode()
    assert "REMISIÓN" in html and "Tote Bag" in html and ">70<" in html
    assert "Av. Juárez 10" in html
    assert "Recibí de conformidad." in html
    # `|dinero` recorta los .00: el precio se imprimiría «$195».
    assert "$195" not in html, "de fábrica la remisión no lleva precios"


def test_la_orden_de_trabajo_no_lleva_precio_de_venta(client, jefe, proyecto):
    client.force_login(jefe)
    html = _ver(client, "orden_trabajo", proyecto.pk).content.decode()
    assert "ORDEN DE TRABAJO" in html and "Tote Bag" in html
    assert "Crea Blanks" in html and "Tinta blanca" in html
    assert "$195" not in html and "$80" not in html, "ni venta ni costo de fábrica"


def test_el_comprobante_de_reembolso(client, jefe, egreso):
    client.force_login(jefe)
    html = _ver(client, "reembolso", egreso.pk).content.decode()
    assert "Tinta para plotter" in html and "Papelería Sol" in html
    assert "TRESCIENTOS OCHENTA PESOS 00/100 M.N." in html
    assert "Recibí el reembolso." in html


# ── 2. Los permisos ─────────────────────────────────────────────────────────


def test_sin_permiso_de_finanzas_no_hay_recibo(client, usuario_factory, ingreso):
    client.force_login(usuario_factory(rol="disenador"))
    assert _ver(client, "recibo_pago", ingreso.pk).status_code == 404
    assert client.get(reverse("imprenta:pdf", args=["recibo_pago", ingreso.pk])).status_code == 404


def test_la_remision_pide_poder_ver_el_proyecto(client, usuario_factory, proyecto):
    from apps.los_proyectos.models import ProyectoAsignacion

    disenador = usuario_factory(rol="disenador")
    client.force_login(disenador)
    assert _ver(client, "remision", proyecto.pk).status_code == 404, "vio un proyecto ajeno"
    ProyectoAsignacion.objects.create(proyecto=proyecto, usuario=disenador)
    assert _ver(client, "remision", proyecto.pk).status_code == 200


def test_un_tipo_inventado_o_un_id_que_no_existe(client, jefe):
    client.force_login(jefe)
    assert _ver(client, "pasaporte", 1).status_code == 404
    assert _ver(client, "recibo_pago", 999999).status_code == 404


# ── 3. El PDF ───────────────────────────────────────────────────────────────


def test_el_pdf_sale_del_motor(client, jefe, ingreso, monkeypatch):
    from lib import gotenberg

    capturado = {}
    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)

    def _convertir(html, pagina=None):
        capturado["pagina"] = pagina
        return b"%PDF-1.4 recibo"

    monkeypatch.setattr(gotenberg, "html_a_pdf", _convertir)
    client.force_login(jefe)
    r = client.get(reverse("imprenta:pdf", args=["recibo_pago", ingreso.pk]))
    assert r.status_code == 200 and r.content == b"%PDF-1.4 recibo"
    assert "RECIBO_DE_PAGO" in r["Content-Disposition"]
    assert capturado["pagina"]["pdfa"] is True, "el recibo se archiva: PDF/A de fábrica"
    assert capturado["pagina"]["metadatos"]["Subject"] == "Heladería Sur"


def test_sin_motor_la_version_imprimible(client, jefe, ingreso, monkeypatch):
    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)
    client.force_login(jefe)
    r = client.get(reverse("imprenta:pdf", args=["recibo_pago", ingreso.pk]))
    assert r.status_code == 302
    assert r["Location"] == reverse("imprenta:ver", args=["recibo_pago", ingreso.pk])


# ── 4. Marcas por estado ────────────────────────────────────────────────────


def test_el_ingreso_anulado_sale_marcado(ingreso):
    from imprenta.documentos import base
    from imprenta.tipos import DOCUMENTOS

    doc = DOCUMENTOS["recibo_pago"]
    assert "marca_agua" not in base.pagina(doc, ingreso, base.configuracion(doc))
    ingreso.anulado = True
    ingreso.save()
    assert base.pagina(doc, ingreso, base.configuracion(doc))["marca_agua"] == "ANULADO"


def test_el_reembolso_por_pagar_sale_marcado(egreso):
    from imprenta.documentos import base
    from imprenta.tipos import DOCUMENTOS

    doc = DOCUMENTOS["reembolso"]
    assert base.pagina(doc, egreso, base.configuracion(doc))["marca_agua"] == "POR PAGAR"


# ── 5. El monto en letra ────────────────────────────────────────────────────


@pytest.mark.parametrize(("monto", "letra"), [
    ("1", "UN PESO 00/100 M.N."),
    ("21", "VEINTIÚN PESOS 00/100 M.N."),
    ("100", "CIEN PESOS 00/100 M.N."),
    ("101", "CIENTO UN PESOS 00/100 M.N."),
    ("1250.50", "MIL DOSCIENTOS CINCUENTA PESOS 50/100 M.N."),
    ("21000", "VEINTIÚN MIL PESOS 00/100 M.N."),
    ("1000000", "UN MILLÓN DE PESOS 00/100 M.N."),
    ("2500000.99", "DOS MILLONES QUINIENTOS MIL PESOS 99/100 M.N."),
])
def test_el_monto_en_letra(monto, letra):
    from imprenta.letras import monto_en_letra

    assert monto_en_letra(Decimal(monto)) == letra


# ── 6. La Gerencia y los botones ────────────────────────────────────────────


def test_cada_documento_tiene_su_boton_en_el_taller(client, jefe, ingreso, egreso, proyecto, cliente):
    client.force_login(jefe)
    ver = reverse("imprenta:ver", args=["recibo_pago", ingreso.pk])
    assert ver in client.get(reverse("tesoreria:ingreso-detalle", args=[ingreso.pk])).content.decode()
    assert ver in client.get(reverse("tesoreria:ingreso-editar", args=[ingreso.pk])).content.decode()
    ver = reverse("imprenta:ver", args=["reembolso", egreso.pk])
    assert ver in client.get(reverse("tesoreria:egreso-detalle", args=[egreso.pk])).content.decode()
    html = client.get(reverse("proyectos-detalle", args=[proyecto.pk])).content.decode()
    assert reverse("imprenta:ver", args=["remision", proyecto.pk]) in html
    assert reverse("imprenta:ver", args=["orden_trabajo", proyecto.pk]) in html
    html = client.get(reverse("cartera-detalle", args=[cliente.pk])).content.decode()
    assert reverse("imprenta:ver", args=["estado_cuenta", cliente.pk]) in html


def test_un_egreso_que_no_es_reembolso_no_ofrece_el_comprobante(client, jefe, egreso):
    egreso.metodo, egreso.estado_pago = "transferencia", "pagado"
    egreso.save()
    client.force_login(jefe)
    html = client.get(reverse("tesoreria:egreso-detalle", args=[egreso.pk])).content.decode()
    assert reverse("imprenta:ver", args=["reembolso", egreso.pk]) not in html


def test_los_ejemplos_siguen_el_permiso_del_modulo(usuario_factory, ingreso):
    """Quien puede ver Documentos pero no Finanzas no ve recibos reales."""
    from cuentas.models.permiso_usuario import PermisoUsuario
    from imprenta.tipos import ejemplos

    jefe = usuario_factory(rol="super_admin")
    assert ejemplos("recibo_pago", usuario=jefe)
    u = usuario_factory(rol="disenador")
    PermisoUsuario.objects.create(usuario=u, modulo="documentos", permiso="ver", activo=True)
    assert ejemplos("recibo_pago", usuario=u) == []


def test_el_chalan_da_el_enlace_de_los_documentos_nuevos(jefe, usuario_factory, ingreso, proyecto, cliente):
    import capacidades

    r = capacidades.ejecutar("enlace_documento", {"tipo": "recibo_pago", "codigo": ingreso.codigo}, jefe)
    assert r["pdf"] == f"/documentos/recibo_pago/{ingreso.pk}/pdf/"
    r = capacidades.ejecutar("enlace_documento", {"tipo": "remision", "codigo": proyecto.codigo}, jefe)
    assert r["pdf"] == f"/documentos/remision/{proyecto.pk}/pdf/"
    r = capacidades.ejecutar("enlace_documento", {"tipo": "estado_cuenta", "codigo": "heladería sur"}, jefe)
    assert r["pdf"] == f"/documentos/estado_cuenta/{cliente.pk}/pdf/"
    ajeno = usuario_factory(rol="disenador")
    r = capacidades.ejecutar("enlace_documento", {"tipo": "remision", "codigo": proyecto.codigo}, ajeno)
    assert "error" in r, "le dio el enlace de un proyecto que no puede ver"
    r = capacidades.ejecutar("enlace_documento", {"tipo": "recibo_pago", "codigo": ingreso.codigo}, ajeno)
    assert "error" in r
