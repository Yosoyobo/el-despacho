"""Compras y la orden de compra (La Imprenta · Deploy 4, 2026-09-29).

Lo que se cuida:

1. **La orden se captura** con sus renglones (los vacíos no se guardan) y su
   folio OC-AAAA-NNNN avanza por año.
2. **Cada acción pide su permiso** (`compras.ver/crear/editar/cancelar`) y una
   orden recibida o cancelada ya no se edita.
3. **El Testigo**: editar no pisa lo que otra persona guardó mientras tanto.
4. **El documento** sale con La Imprenta, marcado BORRADOR o CANCELADA, y sin
   permiso de compras no se ve (404).
5. **La siembra** da `compras` a quien hoy ve el dinero, y a nadie más.
6. **El Chalán** consulta las órdenes (con permiso) y no las crea.
7. **La portada** de la cotización: sólo con el motor propio.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


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
def proveedor():
    from apps.el_catalogo.models import Proveedor

    return Proveedor.objects.create(razon_social="Crea Blanks", activo=True, rfc="CBL010101AA1",
                                    email_contacto="ventas@crea.mx")


@pytest.fixture
def orden(proveedor, jefe):
    from apps.compras.models import OrdenCompra, OrdenCompraItem

    o = OrdenCompra.objects.create(proveedor=proveedor, creado_por=jefe, condiciones="Pago a 15 días")
    OrdenCompraItem.objects.create(orden_compra=o, descripcion="Tote bag cruda", cantidad=Decimal("70"),
                                   precio_unitario=Decimal("38.50"))
    return o


def _con(usuario_factory, *acciones):
    from cuentas.models.permiso_usuario import PermisoUsuario

    u = usuario_factory(rol="disenador")
    PermisoUsuario.objects.filter(usuario=u, modulo="compras").delete()
    for a in ("ver", "crear", "editar", "cancelar"):
        PermisoUsuario.objects.create(usuario=u, modulo="compras", permiso=a, activo=a in acciones)
    return u


def _datos(proveedor, **extra):
    datos = {
        "proveedor": str(proveedor.pk), "fecha": "2026-09-29", "fecha_entrega": "2026-10-10",
        "moneda": "MXN", "condiciones": "", "notas": "",
        "items-TOTAL_FORMS": "3", "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
        "items-0-descripcion": "Playera negra", "items-0-cantidad": "50", "items-0-unidad": "pz",
        "items-0-precio_unitario": "42",
        # Los renglones 1 y 2 van vacíos, como los deja la pantalla.
        "items-1-cantidad": "1.00", "items-1-precio_unitario": "0.00", "items-1-unidad": "pz",
        "items-2-cantidad": "1.00", "items-2-precio_unitario": "0.00", "items-2-unidad": "pz",
    }
    datos.update(extra)
    return datos


# ── 1. Capturar ─────────────────────────────────────────────────────────────


def test_crear_una_orden_con_sus_renglones(client, jefe, proveedor):
    from apps.compras.models import OrdenCompra

    client.force_login(jefe)
    r = client.post(reverse("compras:nueva"), _datos(proveedor))
    assert r.status_code == 302, r.content.decode()[:500]
    o = OrdenCompra.objects.get()
    assert re.fullmatch(r"OC-\d{4}-0001", o.codigo)
    assert [it.descripcion for it in o.items.all()] == ["Playera negra"], "se guardaron renglones vacíos"
    assert o.total == Decimal("2100.00")
    segunda = OrdenCompra.objects.create(proveedor=proveedor, creado_por=jefe)
    assert segunda.codigo.endswith("-0002")


def test_la_lista_y_el_detalle(client, jefe, orden):
    client.force_login(jefe)
    assert orden.codigo in client.get(reverse("compras:lista")).content.decode()
    html = client.get(reverse("compras:detalle", args=[orden.pk])).content.decode()
    assert "Tote bag cruda" in html
    assert reverse("imprenta:ver", args=["orden_compra", orden.pk]) in html


# ── 2. Permisos y estados ───────────────────────────────────────────────────


def test_sin_permiso_no_hay_compras(client, usuario_factory, orden):
    client.force_login(usuario_factory(rol="disenador"))
    assert client.get(reverse("compras:lista")).status_code == 403
    assert client.get(reverse("compras:detalle", args=[orden.pk])).status_code == 403


def test_quien_solo_ve_no_crea_ni_edita_ni_cancela(client, usuario_factory, orden, proveedor):
    client.force_login(_con(usuario_factory, "ver"))
    assert client.get(reverse("compras:lista")).status_code == 200
    assert client.post(reverse("compras:nueva"), _datos(proveedor)).status_code == 403
    assert client.get(reverse("compras:editar", args=[orden.pk])).status_code == 403
    r = client.post(reverse("compras:estado", args=[orden.pk]), {"estado": "cancelada"})
    assert r.status_code == 403
    orden.refresh_from_db()
    assert orden.estado == "borrador"


def test_editar_no_da_permiso_de_cancelar(client, usuario_factory, orden):
    client.force_login(_con(usuario_factory, "ver", "editar"))
    assert client.post(reverse("compras:estado", args=[orden.pk]), {"estado": "enviada"}).status_code == 302
    assert client.post(reverse("compras:estado", args=[orden.pk]), {"estado": "cancelada"}).status_code == 403
    orden.refresh_from_db()
    assert orden.estado == "enviada" and orden.enviada_en is not None


def test_una_orden_recibida_ya_no_se_edita(client, jefe, orden):
    orden.estado = "recibida"
    orden.save()
    client.force_login(jefe)
    r = client.get(reverse("compras:editar", args=[orden.pk]))
    assert r.status_code == 302 and r["Location"].endswith(f"/compras/{orden.pk}/")


# ── 3. El Testigo ───────────────────────────────────────────────────────────


def test_editar_no_pisa_lo_que_guardo_otra_persona(client, jefe, orden, proveedor):
    from lib import edicion

    client.force_login(jefe)
    html = client.get(reverse("compras:editar", args=[orden.pk])).content.decode()
    testigo = re.search(rf'name="{edicion.CAMPO_TESTIGO}"[^>]*value="([^"]*)"', html)
    assert testigo, "el formulario no trae testigo"
    item = orden.items.get()
    # Alguien más cambia las condiciones mientras esta pantalla sigue abierta.
    orden.condiciones = "Pago de contado"
    orden.save()
    datos = _datos(proveedor, **{
        edicion.CAMPO_TESTIGO: testigo.group(1).replace("&quot;", '"'),
        "condiciones": "Pago a 30 días",
        "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1",
        "items-0-id": str(item.pk), "items-0-descripcion": "Tote bag cruda",
        "items-0-cantidad": "70", "items-0-precio_unitario": "38.50",
    })
    r = client.post(reverse("compras:editar", args=[orden.pk]), datos)
    assert r.status_code == 409, "pisó lo que guardó otra persona sin preguntar"
    orden.refresh_from_db()
    assert orden.condiciones == "Pago de contado"


# ── 4. El documento ─────────────────────────────────────────────────────────


def test_el_documento_de_la_orden(client, jefe, orden):
    client.force_login(jefe)
    html = client.get(reverse("imprenta:ver", args=["orden_compra", orden.pk])).content.decode()
    assert "ORDEN DE COMPRA" in html and orden.codigo in html
    assert "Crea Blanks" in html and "CBL010101AA1" in html
    assert "Tote bag cruda" in html and "$38.50" in html
    assert "Pago a 15 días" in html


def test_la_orden_sale_marcada_segun_su_estado(orden):
    from imprenta.documentos import base
    from imprenta.tipos import DOCUMENTOS

    doc = DOCUMENTOS["orden_compra"]
    assert base.pagina(doc, orden, base.configuracion(doc))["marca_agua"] == "BORRADOR"
    orden.estado = "enviada"
    orden.save()
    assert "marca_agua" not in base.pagina(doc, orden, base.configuracion(doc))
    orden.estado = "cancelada"
    orden.save()
    assert base.pagina(doc, orden, base.configuracion(doc))["marca_agua"] == "CANCELADA"


def test_sin_permiso_de_compras_el_documento_no_existe(client, usuario_factory, orden):
    client.force_login(usuario_factory(rol="disenador"))
    assert client.get(reverse("imprenta:ver", args=["orden_compra", orden.pk])).status_code == 404


# ── 5. La siembra ───────────────────────────────────────────────────────────


def test_la_siembra_da_compras_a_quien_ve_el_dinero(usuario_factory):
    import importlib

    from django.apps import apps

    from cuentas.models.permiso_usuario import PermisoUsuario

    con = usuario_factory(rol="contador")
    PermisoUsuario.objects.update_or_create(usuario=con, modulo="tesoreria", permiso="ver",
                                            defaults={"activo": True})
    sin = usuario_factory(rol="disenador")
    PermisoUsuario.objects.filter(usuario=sin, modulo="tesoreria").delete()
    PermisoUsuario.objects.filter(modulo="compras").delete()
    importlib.import_module("apps.compras.migrations.0002_seed_permisos_compras").sembrar(apps, None)

    def acciones(u):
        return set(PermisoUsuario.objects.filter(usuario=u, modulo="compras", activo=True)
                   .values_list("permiso", flat=True))

    assert acciones(con) == {"ver", "crear", "editar", "cancelar"}
    assert acciones(sin) == set()


# ── 6. El Chalán ────────────────────────────────────────────────────────────


def test_el_chalan_consulta_las_ordenes(jefe, usuario_factory, orden):
    import capacidades

    r = capacidades.ejecutar("ordenes_de_compra", {}, jefe)
    assert r["ordenes"][0]["codigo"] == orden.codigo
    assert r["ordenes"][0]["pdf"] == f"/documentos/orden_compra/{orden.pk}/pdf/"
    assert "ordenes_de_compra" not in {c.nombre for c in capacidades.listar(usuario_factory(rol="disenador"))}
    r = capacidades.ejecutar("enlace_documento", {"tipo": "orden_compra", "codigo": orden.codigo}, jefe)
    assert r["pdf"] == f"/documentos/orden_compra/{orden.pk}/pdf/"


def test_el_menu_trae_compras(client, jefe):
    client.force_login(jefe)
    assert 'href="/compras/"' in client.get(reverse("compras:lista")).content.decode()


# ── 7. La portada ───────────────────────────────────────────────────────────


def test_la_portada_solo_con_el_motor_propio(cliente_factory, jefe):
    from apps.cotizaciones import services
    from apps.cotizaciones.models import Cotizacion

    from imprenta.config import resolver
    from imprenta.models import AjusteImprenta

    cot = Cotizacion.objects.create(cliente=cliente_factory(creado_por=jefe), titulo="Termos",
                                    creado_por=jefe, estado="generada")
    assert "page-break-after:always" not in services.construir_html_pdf(cot), "de fábrica, sin portada"
    AjusteImprenta.objects.create(ambito="cotizacion", valores={"portada": True,
                                                                "portada_texto": "Propuesta 2027"})
    from imprenta import config
    config.olvidar()
    html = services.construir_html_pdf(cot, config=resolver("cotizacion"))
    assert "page-break-after:always" in html and "Propuesta 2027" in html
    basico = services.construir_html_pdf(cot, config=resolver("cotizacion", basico=True))
    assert "Propuesta 2027" not in basico, "Google recibió la portada"
