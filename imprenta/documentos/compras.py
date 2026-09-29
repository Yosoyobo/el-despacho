"""La orden de compra al proveedor (La Imprenta · Deploy 4)."""

from __future__ import annotations

from ..esquema import Bloque, Columna, DefinicionTipo, Marca
from .base import Documento

ORDEN_COMPRA_DEF = DefinicionTipo(
    slug="orden_compra",
    nombre="Orden de compra",
    subcarpeta="Órdenes de compra",
    ayuda="Lo que se le pide a un proveedor: qué, cuánto, a qué precio y para cuándo.",
    bloques=(
        Bloque("fecha", "Fecha (arriba a la izquierda)"),
        Bloque("logo", "Logotipo"),
        Bloque("proveedor", "Datos del proveedor"),
        Bloque("proyecto", "Proyecto"),
        Bloque("entrega", "Para cuándo"),
        Bloque("precios", "Precios e importes",
               ayuda="Apagado, la orden sólo dice qué y cuánto."),
        Bloque("condiciones", "Condiciones (pago, entrega, empaque)"),
        Bloque("notas", "Notas"),
    ),
    columnas=(
        Columna("cantidad", "Cant."),
        Columna("descripcion", "Descripción"),
        Columna("precio", "P. unitario"),
        Columna("importe", "Importe"),
        Columna("rotulo_proveedor", "Proveedor"),
        Columna("rotulo_total", "Total"),
        Columna("rotulo_entrega", "Entregar a más tardar el"),
    ),
    # Quién la pide y a dónde se factura: lo que el proveedor necesita.
    datos_default=("razon_social", "rfc", "direccion", "telefono", "correo"),
    firma_default=True,
    aceptacion_texto="Acepto la orden, sus cantidades y precios.",
    qr_opciones=("",),
    marcas=(
        Marca("borrador", "Borrador", "BORRADOR", "#d92d20"),
        Marca("cancelada", "Cancelada", "CANCELADA", "#d92d20"),
    ),
)


def _orden(pk):
    from apps.compras.models import OrdenCompra

    return OrdenCompra.objects.select_related("proveedor", "proyecto").get(pk=pk)


def _puede(usuario, obj=None) -> bool:
    from lib import permisos

    return permisos.puede_ver_compras(usuario)


def _contexto(orden, cfg) -> dict:
    return {"orden": orden, "items": list(orden.items.all()), "total": orden.total,
            "prov": orden.proveedor}


def _piezas(orden) -> dict:
    return {"folio": orden.codigo, "cliente": orden.proveedor.razon_social,
            "proyecto": (orden.proyecto.nombre if orden.proyecto_id else ""),
            "fecha": orden.fecha.strftime("%Y-%m-%d") if orden.fecha else "", "version": ""}


def _ejemplos(limite: int = 15):
    from apps.compras.models import OrdenCompra

    qs = OrdenCompra.objects.select_related("proveedor").order_by("-fecha", "-pk")[:limite]
    return [(o.pk, f"{o.codigo} · {o.proveedor.razon_social}"[:90]) for o in qs]


def _marca(orden, cfg):
    if orden.estado == "cancelada":
        return cfg.marca_de("cancelada")
    if orden.estado == "borrador":
        return cfg.marca_de("borrador")
    return "", ""


ORDEN_COMPRA = Documento(
    definicion=ORDEN_COMPRA_DEF,
    plantilla="imprenta/documentos/orden_compra.html",
    rotulo="Orden de compra",
    obtener=_orden, puede=_puede, contexto=_contexto,
    piezas=_piezas, ejemplos=_ejemplos,
    titulo=lambda o: f"Orden de compra {o.codigo}",
    fecha=lambda o: o.fecha,
    marca=_marca,
)
