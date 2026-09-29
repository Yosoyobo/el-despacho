"""Documentos de La Tesorería: el recibo de pago y el comprobante de reembolso."""

from __future__ import annotations

from ..esquema import Bloque, Columna, DefinicionTipo, Marca
from .base import Documento


def _finanzas(usuario, obj=None) -> bool:
    from lib import permisos

    return permisos.puede_ver_finanzas(usuario)


# ── Recibo de pago (un ingreso) ─────────────────────────────────────────────

RECIBO_PAGO = DefinicionTipo(
    slug="recibo_pago",
    nombre="Recibo de pago",
    subcarpeta="Recibos",
    ayuda="Lo que se le da al cliente cuando paga: sale de un ingreso de La Tesorería.",
    bloques=(
        Bloque("fecha", "Fecha del pago (arriba a la izquierda)"),
        Bloque("logo", "Logotipo"),
        Bloque("letra", "Cantidad con letra"),
        Bloque("factura", "La factura a la que se aplica"),
        Bloque("proyecto", "Proyecto"),
        Bloque("metodo", "Forma de pago y referencia"),
    ),
    columnas=(
        Columna("rotulo_recibimos", "Recibimos de"),
        Columna("rotulo_cantidad", "La cantidad de"),
        Columna("rotulo_concepto", "Por concepto de"),
        Columna("rotulo_factura", "Aplicado a la factura"),
        Columna("rotulo_metodo", "Forma de pago"),
    ),
    datos_default=("razon_social", "rfc"),
    firma_default=True,
    pdfa_default=True,
    marcas=(Marca("anulado", "Anulado", "ANULADO", "#d92d20"),),
)


def _ingreso(pk):
    from apps.tesoreria.models import Ingreso

    return Ingreso.objects.select_related("cliente", "proyecto", "factura").get(pk=pk)


def _recibo_contexto(ing, cfg) -> dict:
    from ..letras import monto_en_letra

    return {
        "ing": ing,
        "monto_letra": monto_en_letra(ing.monto, ing.moneda),
        "metodo": ing.get_metodo_display(),
    }


def _recibo_piezas(ing) -> dict:
    return {
        "folio": ing.codigo,
        "cliente": ing.cliente.razon_social if ing.cliente_id else "",
        "proyecto": ing.proyecto.nombre if ing.proyecto_id else "",
        "fecha": ing.fecha.strftime("%Y-%m-%d") if ing.fecha else "",
        "version": "",
    }


def _recibo_ejemplos(limite: int = 15):
    from apps.tesoreria.models import Ingreso

    qs = Ingreso.objects.filter(anulado=False).select_related("cliente").order_by("-fecha", "-pk")[:limite]
    return [(i.pk, f"{i.codigo} · {getattr(i.cliente, 'razon_social', '—')} · ${i.monto:,.2f}"[:90])
            for i in qs]


RECIBO = Documento(
    definicion=RECIBO_PAGO,
    plantilla="imprenta/documentos/recibo_pago.html",
    rotulo="Recibo de pago",
    obtener=_ingreso, puede=_finanzas, contexto=_recibo_contexto,
    piezas=_recibo_piezas, ejemplos=_recibo_ejemplos,
    titulo=lambda ing: f"Recibo de pago {ing.codigo}",
    fecha=lambda ing: ing.fecha,
    marca=lambda ing, cfg: cfg.marca_de("anulado") if ing.anulado else ("", ""),
)


# ── Comprobante de reembolso (un egreso pagado de la bolsa de alguien) ──────

REEMBOLSO_DEF = DefinicionTipo(
    slug="reembolso",
    nombre="Comprobante de reembolso",
    subcarpeta="Reembolsos",
    ayuda="Cuando el despacho le devuelve a alguien del equipo lo que pagó de su bolsa.",
    bloques=(
        Bloque("fecha", "Fecha (arriba a la izquierda)"),
        Bloque("logo", "Logotipo"),
        Bloque("letra", "Cantidad con letra"),
        Bloque("proveedor", "A quién se le compró"),
        Bloque("proyecto", "Proyecto y centro de costo"),
        Bloque("pago", "Cuándo y de dónde se pagó"),
    ),
    columnas=(
        Columna("rotulo_persona", "Se reembolsa a"),
        Columna("rotulo_cantidad", "La cantidad de"),
        Columna("rotulo_concepto", "Por"),
    ),
    firma_default=True,
    aceptacion_default=True,
    aceptacion_texto="Recibí el reembolso.",
    qr_opciones=("",),
    marcas=(
        Marca("pendiente", "Por pagar", "POR PAGAR", "#f79009"),
        Marca("anulado", "Anulado", "ANULADO", "#d92d20"),
    ),
)


def _egreso(pk):
    from apps.tesoreria.models import Egreso

    return Egreso.objects.select_related("proveedor", "proyecto", "centro_de_costo",
                                         "pagado_por", "solicitado_por").get(pk=pk)


def _persona(eg) -> str:
    u = eg.solicitado_por or eg.pagado_por
    if u is None:
        return ""
    return (getattr(u, "nombre_completo", "") or "").strip() or u.email


def _reembolso_contexto(eg, cfg) -> dict:
    from ..letras import monto_en_letra

    return {"eg": eg, "persona": _persona(eg), "monto_letra": monto_en_letra(eg.monto, eg.moneda),
            "proveedor": (eg.proveedor.razon_social if eg.proveedor_id else eg.proveedor_nombre),
            "metodo": eg.get_metodo_display()}


def _reembolso_piezas(eg) -> dict:
    return {"folio": eg.codigo, "cliente": _persona(eg),
            "proyecto": eg.proyecto.nombre if eg.proyecto_id else "",
            "fecha": eg.fecha.strftime("%Y-%m-%d") if eg.fecha else "", "version": ""}


def _es_reembolso(eg) -> bool:
    from apps.tesoreria.models.egreso import METODOS_REEMBOLSO

    return eg.metodo in METODOS_REEMBOLSO or eg.estado_pago == "por_reembolsar"


def _reembolso_ejemplos(limite: int = 15):
    from apps.tesoreria.models import Egreso
    from apps.tesoreria.models.egreso import METODOS_REEMBOLSO

    qs = (Egreso.objects.filter(anulado=False, metodo__in=list(METODOS_REEMBOLSO))
          .order_by("-fecha", "-pk")[:limite])
    return [(e.pk, f"{e.codigo} · {e.descripcion} · ${e.monto:,.2f}"[:90]) for e in qs]


def _reembolso_marca(eg, cfg):
    if eg.anulado:
        return cfg.marca_de("anulado")
    if eg.estado_pago in ("por_reembolsar", "pendiente"):
        return cfg.marca_de("pendiente")
    return "", ""


REEMBOLSO = Documento(
    definicion=REEMBOLSO_DEF,
    plantilla="imprenta/documentos/reembolso.html",
    rotulo="Reembolso",
    obtener=_egreso, puede=_finanzas, contexto=_reembolso_contexto,
    piezas=_reembolso_piezas, ejemplos=_reembolso_ejemplos,
    titulo=lambda eg: f"Comprobante de reembolso {eg.codigo}",
    fecha=lambda eg: eg.pagado_en or eg.fecha,
    marca=_reembolso_marca,
    extra={"aplica": _es_reembolso},
)
