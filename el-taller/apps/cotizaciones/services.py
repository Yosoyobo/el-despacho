"""Services de Las Cotizaciones.

Cubre transiciones de estado y emisión de eventos Portavoz.
Los cálculos viven en `Cotizacion.calcular_totales` para que el detalle
sea consultable sin importar este módulo.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Cotizacion


def _emitir(tipo: str, cot: Cotizacion, actor, payload_extra: dict | None = None):
    payload = {
        "cotizacion_id": cot.id,
        "codigo": cot.codigo,
        "cliente_id": cot.cliente_id,
        "estado": cot.estado,
    }
    if payload_extra:
        payload.update(payload_extra)
    emitir(EventoPortavoz(
        tipo=tipo,
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload=payload,
    ))


def emitir_creada(cot: Cotizacion, actor):
    _emitir("cotizacion.creada", cot, actor, {"titulo": cot.titulo})


def construir_html_pdf(cot: Cotizacion) -> str:
    """Renderiza el HTML imprimible de la cotización (template `pdf.html`)."""
    from django.template.loader import render_to_string
    return render_to_string("cotizaciones/pdf.html", {
        "cot": cot,
        "items": list(cot.items.select_related("servicio", "unidad_fk").all()),
        "totales": cot.calcular_totales(),
    })


def generar_pdf(cot: Cotizacion, actor):
    """Genera (o regenera) el PDF de la cotización vía Google Docs y lo guarda
    en Drive. Devuelve `lib.documentos.ResultadoPdf`. Borra el PDF anterior si
    lo había. Fallback gracioso (nunca lanza)."""
    from lib.documentos import generar_pdf as _gen
    from lib.google_drive import drive

    html = construir_html_pdf(cot)
    res = _gen(html=html, nombre=cot.codigo, subcarpeta="Cotizaciones")
    if not res.ok:
        return res

    # Borra el PDF previo (best-effort) antes de apuntar al nuevo.
    if cot.pdf_file_id and cot.pdf_file_id != res.data.get("id"):
        import contextlib
        with contextlib.suppress(Exception):
            drive.borrar(cot.pdf_file_id)

    cot.pdf_file_id = res.data.get("id", "")
    cot.pdf_url = res.data.get("webViewLink", "")
    cot.pdf_generado_en = timezone.now()
    cot.save(update_fields=["pdf_file_id", "pdf_url", "pdf_generado_en"])
    _emitir("cotizacion.pdf_generado", cot, actor, {"pdf_file_id": cot.pdf_file_id})
    return res


def emitir_actualizada(cot: Cotizacion, actor):
    _emitir("cotizacion.actualizada", cot, actor)


def marcar_enviada(cot: Cotizacion, actor, email_destino: str = "") -> Cotizacion:
    if cot.estado != "borrador":
        raise ValueError("Solo se puede enviar una cotización en borrador.")
    with transaction.atomic():
        cot.estado = "enviada"
        cot.enviada_en = timezone.now()
        cot.enviada_a_email = email_destino or cot.enviada_a_email or (
            getattr(cot.cliente, "email_contacto", "") or ""
        )
        cot.save(update_fields=["estado", "enviada_en", "enviada_a_email", "actualizado_en"])
    _emitir("cotizacion.enviada", cot, actor, {"email_destino": cot.enviada_a_email})
    return cot


def marcar_aprobada(cot: Cotizacion, actor, nombre: str, email: str = "",
                    referencia: str = "") -> Cotizacion:
    if cot.estado != "enviada":
        raise ValueError("Solo se puede aprobar una cotización enviada.")
    if not nombre.strip():
        raise ValueError("Debe registrarse el nombre de quien aprobó.")
    with transaction.atomic():
        cot.estado = "aprobada"
        cot.aprobada_en = timezone.now()
        cot.aprobada_por_nombre = nombre.strip()
        cot.aprobada_por_email = email.strip()
        cot.referencia_aprobacion = referencia.strip()
        cot.save(update_fields=[
            "estado", "aprobada_en", "aprobada_por_nombre",
            "aprobada_por_email", "referencia_aprobacion", "actualizado_en",
        ])
    _emitir("cotizacion.aprobada", cot, actor, {
        "aprobada_por": cot.aprobada_por_nombre,
    })
    return cot


def marcar_rechazada(cot: Cotizacion, actor, motivo: str) -> Cotizacion:
    if cot.estado != "enviada":
        raise ValueError("Solo se puede rechazar una cotización enviada.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Debe registrarse el motivo de rechazo.")
    with transaction.atomic():
        cot.estado = "rechazada"
        cot.rechazada_en = timezone.now()
        cot.motivo_rechazo = motivo
        cot.save(update_fields=["estado", "rechazada_en", "motivo_rechazo", "actualizado_en"])
    _emitir("cotizacion.rechazada", cot, actor, {"motivo": motivo[:200]})
    return cot


def marcar_anulada(cot: Cotizacion, actor, motivo: str) -> Cotizacion:
    if cot.estado == "anulada":
        raise ValueError("La cotización ya estaba anulada.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Debe registrarse el motivo de anulación.")
    with transaction.atomic():
        cot.estado = "anulada"
        cot.anulada_en = timezone.now()
        cot.anulada_por = actor if getattr(actor, "is_authenticated", False) else None
        cot.motivo_anulacion = motivo[:300]
        cot.save(update_fields=[
            "estado", "anulada_en", "anulada_por", "motivo_anulacion", "actualizado_en",
        ])
    _emitir("cotizacion.anulada", cot, actor, {"motivo": motivo[:200]})
    return cot


def duplicar(cot: Cotizacion, actor) -> Cotizacion:
    """Crea una copia en estado borrador con los mismos items e impuestos."""
    from .models import CotizacionImpuesto, CotizacionItem
    with transaction.atomic():
        nueva = Cotizacion.objects.create(
            cliente=cot.cliente,
            proyecto=cot.proyecto,
            titulo=f"Copia de {cot.titulo}"[:200],
            estado="borrador",
            moneda=cot.moneda,
            descuento_global_porcentaje=cot.descuento_global_porcentaje,
            notas=cot.notas,
            terminos=cot.terminos,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        for it in cot.items.all():
            CotizacionItem.objects.create(
                cotizacion=nueva,
                orden=it.orden,
                servicio=it.servicio,
                descripcion=it.descripcion,
                cantidad=it.cantidad,
                unidad=it.unidad,
                precio_unitario=it.precio_unitario,
                descuento_porcentaje=it.descuento_porcentaje,
            )
        for ci in cot.impuestos.all():
            CotizacionImpuesto.objects.create(cotizacion=nueva, tasa=ci.tasa)
    emitir_creada(nueva, actor)
    return nueva


def crear_factura_anticipo(cot: Cotizacion, actor) -> Factura:  # noqa: F821
    """Genera una Factura por el monto del anticipo de la cotización.

    Requiere `cot.anticipo_pendiente == True`. Crea la factura en
    estado 'borrador' con:
    - monto = `cot.anticipo_monto` (línea única)
    - cliente, proyecto: heredados de la cotización
    - cotizacion_origen = esta cotización
    - titulo = "Anticipo de {COT-XXXX}"
    - notas mencionan el anticipo

    Marca `cot.anticipo_facturado_en = now`. Idempotente: si ya fue
    facturado, levanta `ValueError`.
    """
    from datetime import date as _date
    from decimal import Decimal as _Decimal

    if cot.estado != "aprobada":
        raise ValueError("Solo se puede generar factura de anticipo desde una cotización aprobada.")
    if cot.anticipo_monto <= 0:
        raise ValueError("Esta cotización no tiene anticipo configurado.")
    if cot.anticipo_facturado_en is not None:
        raise ValueError("Ya se generó la factura del anticipo para esta cotización.")

    from apps.facturacion.models import Factura, FacturaItem

    monto = cot.anticipo_monto
    with transaction.atomic():
        factura = Factura.objects.create(
            cliente=cot.cliente,
            proyecto=cot.proyecto,
            cotizacion_origen=cot,
            titulo=f"Anticipo de {cot.codigo}",
            estado="borrador",
            fecha_emision=_date.today(),
            moneda=cot.moneda,
            descuento_global_porcentaje=_Decimal("0"),
            notas=f"Anticipo del {cot.anticipo_porcentaje}% sobre {cot.codigo}.\n\n{cot.notas}".strip(),
            terminos=cot.terminos,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        FacturaItem.objects.create(
            factura=factura,
            orden=0,
            descripcion=f"Anticipo · {cot.titulo}",
            cantidad=_Decimal("1.00"),
            unidad="servicio",
            precio_unitario=monto,
            descuento_porcentaje=_Decimal("0.00"),
        )
        cot.anticipo_facturado_en = timezone.now()
        cot.save(update_fields=["anticipo_facturado_en", "actualizado_en"])

    _emitir("cotizacion.anticipo_facturado", cot, actor, {
        "factura_id": factura.pk,
        "factura_codigo": factura.codigo,
        "anticipo_monto": float(monto),
    })
    return factura


# --- KPIs ----------------------------------------------------------------

def kpis_landing() -> dict:
    """Conteos para el header de la lista de Cotizaciones."""
    qs = Cotizacion.objects.exclude(estado="anulada")
    from datetime import date
    aprobadas = qs.filter(estado="aprobada", anticipo_facturado_en__isnull=True)
    # Aprobadas con anticipo pendiente: hay que iterar porque anticipo_monto
    # es property derivada. Sobre 5 usuarios el conjunto es pequeño.
    anticipos_pendientes = sum(1 for c in aprobadas if c.anticipo_monto > 0)
    return {
        "borradores": qs.filter(estado="borrador").count(),
        "enviadas": qs.filter(estado="enviada").count(),
        "aprobadas": qs.filter(estado="aprobada").count(),
        "vencidas": qs.filter(
            estado="enviada", fecha_validez__lt=date.today()
        ).count(),
        "anticipos_pendientes": anticipos_pendientes,
    }


def cotizaciones_con_anticipo_pendiente():
    """Lista de cotizaciones aprobadas con `anticipo_pendiente=True`.

    Útil para CxC unificado (S-Finanzas-V2 #D) y KPIs. Itera porque
    `anticipo_monto` es una property derivada; sobre 5 usuarios el
    conjunto es pequeño (< 50 por mes esperado).
    """
    qs = (
        Cotizacion.objects.filter(estado="aprobada", anticipo_facturado_en__isnull=True)
        .select_related("cliente", "proyecto")
        .order_by("-aprobada_en")
    )
    return [c for c in qs if c.anticipo_monto > 0]
