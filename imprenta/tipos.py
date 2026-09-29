"""Los tipos de documento que arma La Imprenta.

Cada tipo declara la forma de sus ajustes (`esquema.DefinicionTipo`) y cómo se
dibuja un documento real (`Adaptador`). El registro vive aquí y no en cada app
para que La Gerencia pueda listar los tipos y previsualizarlos sin conocer los
detalles de cada módulo: todo lo que toca un modelo se importa **dentro** de la
función, así un tipo cuya app no está en un proyecto sencillamente no ofrece
ejemplos ahí, en vez de tumbar el arranque.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .esquema import Bloque, Columna, DefinicionTipo, Marca

#: Las notas con las que Learning Center cotiza (antes fijas en
#: `apps.cotizaciones.notas`; desde La Imprenta se editan en La Gerencia).
NOTAS_COTIZACION = (
    "Precios unitarios de producción.",
    "Todo detalle está abierto a cambios, nuevas ideas y necesidades.",
    "Las imágenes son ilustrativas y no representan productos finales exactos.",
    "Debido a procesos manuales y características de los materiales, pueden "
    "existir leves variaciones en color, tamaño y acabado respecto a "
    "indicaciones o referencias.",
    "No nos hacemos responsables por retrasos ocasionados por proveedores "
    "externos o causas de fuerza mayor.",
    "Todos los productos sujetos a existencias.",
    "Los precios no incluyen IVA.",
)

# ── Cotización ──────────────────────────────────────────────────────────────

COTIZACION = DefinicionTipo(
    slug="cotizacion",
    nombre="Cotización",
    subcarpeta="Cotizaciones",
    ayuda="La propuesta que se le manda al cliente.",
    bloques=(
        Bloque("fecha", "Fecha (arriba a la izquierda)"),
        Bloque("logo", "Logotipo"),
        Bloque("cliente", "Nombre del cliente (arriba a la derecha)"),
        Bloque("numeracion", "Número de cada concepto"),
        Bloque("fotos", "Foto de cada concepto"),
        Bloque("descripcion", "Especificaciones de cada concepto"),
        Bloque("montos", "Tablita de montos de cada concepto"),
        Bloque("desglose", "Desglose e impuestos",
               ayuda="Sólo sale cuando la cotización lo tiene encendido."),
        Bloque("notas", "Notas"),
        Bloque("condiciones", "Condiciones adicionales",
               ayuda="Las que se escriben en cada cotización."),
    ),
    columnas=(
        Columna("concepto", "Concepto"),
        Columna("cantidad", "Cantidad"),
        Columna("precio", "P. Unitario"),
        Columna("subtotal", "Subtotal"),
        Columna("titulo_desglose", "Desglose de Elementos"),
        Columna("rotulo_subtotal", "Subtotal"),
        Columna("rotulo_total", "Total"),
        Columna("rotulo_notas", "Notas:"),
        Columna("rotulo_condiciones", "Condiciones adicionales"),
    ),
    vigencia=True,
    notas_default=NOTAS_COTIZACION,
    nota_automatica="la forma de pago (anticipo o un solo pago)",
    aceptacion_texto="Acepto esta cotización y sus condiciones.",
    qr_opciones=("", "pago", "portal"),
    # La de «sin enviar» sigue siendo la de la hoja general (BORRADOR); éstas son
    # las demás y nacen vacías: el documento de siempre no lleva ninguna.
    marcas=(
        Marca("aprobada", "Aprobada", "", "#12b76a"),
        Marca("perdida", "Rechazada o anulada", "", "#d92d20"),
        Marca("vencida", "Vencida", "", "#f79009"),
    ),
)


# ── Factura (comercial, no fiscal) ─────────────────────────────────────────

FACTURA = DefinicionTipo(
    slug="factura",
    nombre="Factura",
    subcarpeta="Facturas",
    ayuda="La factura comercial (no es el CFDI: ése lo timbra el contador y se sube aparte).",
    bloques=(
        Bloque("fecha", "Fecha de emisión (arriba a la izquierda)"),
        Bloque("logo", "Logotipo"),
        Bloque("cliente", "Datos del cliente (razón social, RFC, correo, teléfono)"),
        Bloque("fechas", "Emisión, vencimiento y moneda"),
        Bloque("proyecto", "Proyecto"),
        Bloque("descuento", "Columna de descuento"),
        Bloque("saldo", "Cobrado y saldo pendiente"),
        Bloque("pago_en_linea", "Recuadro de pago en línea",
               ayuda="Sólo sale si La Caja está encendida y hay saldo."),
        Bloque("notas", "Notas de la factura"),
        Bloque("terminos", "Términos de la factura"),
    ),
    columnas=(
        Columna("descripcion", "Descripción"),
        Columna("cantidad", "Cant."),
        Columna("precio", "P. unitario"),
        Columna("descuento", "Desc."),
        Columna("importe", "Importe"),
        Columna("rotulo_cliente", "Cliente"),
        Columna("rotulo_subtotal", "Subtotal"),
        Columna("rotulo_total", "TOTAL"),
        Columna("rotulo_notas", "Notas"),
    ),
    # Lo más útil al que paga: con qué razón social, RFC y a qué cuenta. Salen
    # sólo si se capturaron en «Datos y firma».
    datos_default=("razon_social", "rfc", "direccion", "bancarios"),
    qr_opciones=("", "pago", "portal"),
    pdfa_default=True,
    marcas=(
        Marca("borrador", "Borrador", "BORRADOR", "#d92d20"),
        Marca("pagada", "Pagada", "PAGADA", "#12b76a"),
        Marca("cancelada", "Cancelada", "CANCELADA", "#d92d20"),
        Marca("vencida", "Vencida", "VENCIDA", "#f79009"),
    ),
)


@dataclass(frozen=True)
class Adaptador:
    """Cómo se dibuja un documento de verdad para la vista previa y el PDF.

    - `ejemplos(limite)` → `[(id, etiqueta)]` de documentos reales recientes.
    - `html(id, config, preview)` → el HTML del documento con esa configuración.
    - `pagina(id, config)` → el diccionario de hoja que espera el generador.
    """

    ejemplos: Callable[[int], list[tuple[int, str]]]
    html: Callable[..., str]
    pagina: Callable[..., dict]
    #: Quién puede ver documentos REALES de este tipo (la vista previa de La
    #: Gerencia enseña montos y datos de clientes: sólo a quien ya los ve).
    puede: Callable[[object], bool] = lambda usuario: False


def _cot_ejemplos(limite: int = 15) -> list[tuple[int, str]]:
    from apps.cotizaciones.models import Cotizacion

    qs = (Cotizacion.objects.select_related("cliente")
          .order_by("-actualizado_en")[:limite])
    return [(c.pk, f"{c.codigo} · {c.cliente.razon_social} · {c.titulo}"[:90]) for c in qs]


def _cot_html(pk: int, config, preview: bool = True, **kwargs) -> str:
    from apps.cotizaciones import services
    from apps.cotizaciones.models import Cotizacion

    cot = Cotizacion.objects.select_related("cliente", "proyecto").get(pk=pk)
    return services.construir_html_pdf(cot, preview=preview, config=config, **kwargs)


def _cot_pagina(pk: int, config) -> dict:
    from apps.cotizaciones import services
    from apps.cotizaciones.models import Cotizacion

    cot = Cotizacion.objects.select_related("cliente", "proyecto").get(pk=pk)
    return services.pagina_documento(cot, config=config)


def _fac_ejemplos(limite: int = 15) -> list[tuple[int, str]]:
    from apps.facturacion.models import Factura

    qs = Factura.objects.select_related("cliente").order_by("-actualizado_en")[:limite]
    return [(f.pk, f"{f.folio or f.codigo} · {f.cliente.razon_social} · "
                   f"{f.concepto or f.titulo}"[:90]) for f in qs]


def _fac_html(pk: int, config, preview: bool = True, **kwargs) -> str:
    from apps.facturacion import services
    from apps.facturacion.models import Factura

    fac = Factura.objects.select_related("cliente", "proyecto").get(pk=pk)
    return services.construir_html_pdf(fac, config=config, preview=preview, **kwargs)


def _fac_pagina(pk: int, config) -> dict:
    from apps.facturacion import services
    from apps.facturacion.models import Factura

    return services.pagina_documento(Factura.objects.get(pk=pk), config=config)


def _puede_cot(usuario) -> bool:
    from lib import permisos

    return permisos.puede_ver_cotizaciones(usuario)


def _puede_fac(usuario) -> bool:
    from lib import permisos

    return permisos.puede_ver_facturacion(usuario)


def _adaptador_de(doc) -> Adaptador:
    """El adaptador de un `imprenta.documentos.base.Documento`: todos iguales."""
    from .documentos import base

    def html(pk, cfg, preview=True, **kwargs):
        return base.dibujar(doc, doc.obtener(pk), cfg, preview=preview, **kwargs)

    def pagina(pk, cfg):
        return base.pagina(doc, doc.obtener(pk), cfg)

    return Adaptador(doc.ejemplos, html, pagina, puede=lambda u: doc.puede(u, None))


def _documentos() -> dict:
    from .documentos.cartera import ESTADO_CUENTA
    from .documentos.proyectos import ORDEN_TRABAJO, REMISION
    from .documentos.tesoreria import RECIBO, REEMBOLSO

    return {d.slug: d for d in (RECIBO, ESTADO_CUENTA, REMISION, ORDEN_TRABAJO, REEMBOLSO)}


#: slug → `Documento` de los tipos nuevos (Deploy 3 en adelante).
DOCUMENTOS = _documentos()

#: slug → (definición, adaptador). El orden es el de las pestañas.
TIPOS: dict[str, tuple[DefinicionTipo, Adaptador]] = {
    "cotizacion": (COTIZACION, Adaptador(_cot_ejemplos, _cot_html, _cot_pagina, puede=_puede_cot)),
    "factura": (FACTURA, Adaptador(_fac_ejemplos, _fac_html, _fac_pagina, puede=_puede_fac)),
    **{slug: (doc.definicion, _adaptador_de(doc)) for slug, doc in DOCUMENTOS.items()},
}


def definicion(slug: str) -> DefinicionTipo | None:
    par = TIPOS.get(slug)
    return par[0] if par else None


def adaptador(slug: str) -> Adaptador | None:
    par = TIPOS.get(slug)
    return par[1] if par else None


def ejemplos(slug: str, limite: int = 15, usuario=None) -> list[tuple[int, str]]:
    """Documentos reales para la vista previa. [] si la app no está aquí o si
    `usuario` no puede ver documentos de ese tipo."""
    ad = adaptador(slug)
    if ad is None:
        return []
    if usuario is not None:
        try:
            if not ad.puede(usuario):
                return []
        except Exception:  # noqa: BLE001
            return []
    try:
        return ad.ejemplos(limite)
    except Exception:  # noqa: BLE001 — sin la app o sin tabla, no hay ejemplos
        return []


__all__ = ["COTIZACION", "DOCUMENTOS", "FACTURA", "NOTAS_COTIZACION", "TIPOS", "Adaptador", "adaptador", "definicion", "ejemplos"]
