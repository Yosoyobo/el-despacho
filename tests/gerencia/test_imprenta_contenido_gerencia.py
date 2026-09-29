"""La Imprenta · Deploy 2 — lo que se prueba desde La Gerencia (sus rutas viven aquí).

Ver `tests/test_imprenta_contenido.py` para el resto.

Lo que se cuida:

1. **Las notas se editan en La Gerencia** (orden, apagar, agregar) y cada
   cotización puede quitar alguna o sumar las suyas; se heredan a la versión
   siguiente y al duplicar. Las de fábrica son las de siempre.
2. **Las notas tienen su propio permiso**: quien cambia el estilo no cambia lo
   que el cliente acepta.
3. **Firma, aceptación, folio, vigencia y QR** salen cuando se encienden; el QR
   nunca en la versión de Google.
4. **Marcas por estado**: de fábrica sólo BORRADOR (lo de siempre); las demás
   cuando se escriben.
5. **El nombre del archivo** sigue el patrón.
6. **La factura** se arma con La Imprenta: su PDF comercial sale del motor, se
   adjunta al correo cuando no hay CFDI, y la leyenda «no es un CFDI» no se va.
"""

from __future__ import annotations

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
def cot(cliente_factory, jefe):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem

    c = Cotizacion.objects.create(cliente=cliente_factory(creado_por=jefe, razon_social="Optimist"),
                                  titulo="Termos", creado_por=jefe, estado="generada")
    CotizacionItem.objects.create(cotizacion=c, orden=0, concepto="Termo",
                                  cantidad=Decimal("10"), precio_unitario=Decimal("100"))
    return c


@pytest.fixture
def fac(cliente_factory, jefe):
    from apps.facturacion.models import Factura, FacturaItem

    f = Factura.objects.create(cliente=cliente_factory(creado_por=jefe, razon_social="Heladería Sur",
                                                       rfc="HSU010101AB1"),
                               titulo="Producción de vasos", creado_por=jefe)
    FacturaItem.objects.create(factura=f, orden=0, descripcion="Vasos", cantidad=Decimal("1"),
                               unidad="pieza", precio_unitario=Decimal("1000.00"))
    return f


def test_la_gerencia_guarda_las_notas_del_formulario(client, jefe):
    """Campos repetidos en el orden de la pantalla; la nueva recibe id."""
    from imprenta.config import resolver

    client.force_login(jefe)
    client.post(reverse("ajustes-documentos"), {
        "seccion": "cotizacion",
        "cotizacion__notas__id": ["n2", "", "n1"],
        "cotizacion__notas__texto": ["Dos", "Nueva", "Uno"],
        "cotizacion__notas__activa": ["n2"],          # n1 apagada; la nueva, activa
        "cotizacion__bloque_notas": "on", "cotizacion__nota_automatica": "on",
    })
    notas = resolver("cotizacion").doc["notas"]
    assert [n["texto"] for n in notas] == ["Dos", "Nueva", "Uno"]
    assert [n["activa"] for n in notas] == [True, True, False]
    assert notas[1]["id"].startswith("n") and notas[1]["id"] not in {"n1", "n2"}


def test_quien_cambia_el_estilo_no_cambia_las_notas(client, usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    from imprenta.config import resolver
    from imprenta.tipos import NOTAS_COTIZACION

    u = usuario_factory(rol="dueno")
    PermisoUsuario.objects.filter(usuario=u, modulo="documentos").delete()
    for accion in ("ver", "editar_estilo"):
        PermisoUsuario.objects.create(usuario=u, modulo="documentos", permiso=accion, activo=True)
    client.force_login(u)
    r = client.post(reverse("ajustes-documentos"), {
        "seccion": "cotizacion", "cotizacion__col_precio": "Precio c/u",
        "cotizacion__notas__id": ["n1"], "cotizacion__notas__texto": ["Sin garantía."],
        "cotizacion__notas__activa": ["n1"]})
    assert r.status_code == 302
    doc = resolver("cotizacion").doc
    assert doc["col_precio"] == "Precio c/u", "el estilo sí se guarda"
    assert [n["texto"] for n in doc["notas"]] == list(NOTAS_COTIZACION), "cambió las notas sin permiso"


def test_la_vista_previa_de_la_gerencia_dibuja_la_factura(client, jefe, fac):
    client.force_login(jefe)
    r = client.post(reverse("ajustes-documentos-vista"), {
        "seccion": "factura", "tipo": "factura", "ejemplo": str(fac.pk),
        "factura__col_importe": "Monto", "factura__bloque_cliente": "on"})
    html = r.content.decode()
    assert ">Monto<" in html and "Heladería Sur" in html
    assert "lc-hoja" in html
