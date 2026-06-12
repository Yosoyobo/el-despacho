"""La Cobranza — recordatorios de pago automáticos al cliente.

Manda un correo (vía El Cartero, plantilla `cobranza`) al cliente cuando
una factura está vencida (o por vencer, si se configura). La cadencia vive
en `ajustes.ConfiguracionCobranza`. Cada envío (o intento) se audita en
`RecordatorioCobranza`. Diseño defensivo: nunca lanza — registra el fallo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Factura, RecordatorioCobranza

CERO = Decimal("0.00")


def facturas_a_recordar(*, hoy: date | None = None, config=None) -> list[dict]:
    """Lista de `{factura, tipo, dias}` que tocan recordatorio hoy según la
    política. `tipo` ∈ {"mora", "pre_vencimiento"}."""
    from ajustes.models import ConfiguracionCobranza
    hoy = hoy or date.today()
    config = config or ConfiguracionCobranza.obtener()

    candidatas = Factura.objects.filter(
        estado__in=["emitida", "cobrada_parcial"]
    ).select_related("cliente")

    salida: list[dict] = []
    for fac in candidatas:
        if fac.saldo_pendiente <= 0:
            continue
        dias = (hoy - fac.fecha_vencimiento).days
        if dias > 0:
            tipo = "mora"
        elif config.recordar_pre_vencimiento_dias and dias == -config.recordar_pre_vencimiento_dias:
            tipo = "pre_vencimiento"
        else:
            continue

        # Cadencia: no repetir antes de `dias_entre_recordatorios`.
        ultimo = fac.recordatorios.order_by("-enviado_en").first()
        if ultimo and (hoy - ultimo.enviado_en.date()).days < config.dias_entre_recordatorios:
            continue
        # Tope de recordatorios enviados con éxito.
        if config.max_recordatorios:
            enviados_ok = fac.recordatorios.filter(ok=True).count()
            if enviados_ok >= config.max_recordatorios:
                continue
        salida.append({"factura": fac, "tipo": tipo, "dias": dias})
    return salida


def enviar_recordatorio(fac: Factura, *, config=None, tipo: str = "mora",
                        actor=None) -> RecordatorioCobranza:
    """Compone y manda el recordatorio; audita el resultado. Nunca lanza."""
    from ajustes.models import ConfiguracionCobranza
    from cuentas.templatetags.forms_helpers import dinero
    from lib import cartero

    config = config or ConfiguracionCobranza.obtener()
    hoy = date.today()
    dias = (hoy - fac.fecha_vencimiento).days
    saldo = fac.saldo_pendiente
    destino = (getattr(fac.cliente, "email_contacto", "") or "").strip()

    if not destino:
        rec = RecordatorioCobranza.objects.create(
            factura=fac, tipo=tipo, dias_vencida=dias, saldo=saldo,
            ok=False, detalle="El cliente no tiene correo registrado.",
        )
        _emitir_recordatorio(rec, fac, actor)
        return rec

    contexto = {
        "codigo": fac.codigo,
        "cliente": fac.cliente.razon_social,
        "saldo": dinero(saldo),
        "moneda": fac.moneda,
        "vencimiento": fac.fecha_vencimiento.strftime("%d/%m/%Y") if fac.fecha_vencimiento else "",
        "dias_vencida": dias if dias > 0 else 0,
    }
    try:
        from ajustes.models import PlantillaCorreo
        asunto, html = PlantillaCorreo.obtener("cobranza").render(contexto)
    except Exception:  # noqa: BLE001
        asunto = f"Recordatorio de pago · Factura {fac.codigo}"
        html = (f"<p>Estimado/a {fac.cliente.razon_social}:</p>"
                f"<p>La factura {fac.codigo} tiene un saldo pendiente de "
                f"{dinero(saldo)} {fac.moneda}.</p>")

    adjuntos = []
    if config.incluir_pdf:
        try:
            from . import services
            res_pdf = services.generar_pdf(fac, actor)
            if getattr(res_pdf, "ok", False) and getattr(res_pdf, "pdf_bytes", None):
                adjuntos.append(cartero.Adjunto(
                    nombre=f"{fac.codigo}.pdf", contenido=res_pdf.pdf_bytes, mime="application/pdf"))
        except Exception:  # noqa: BLE001 — el PDF no debe tumbar el recordatorio
            pass

    res = cartero.enviar(destinatario=destino, asunto=asunto, html=html, adjuntos=adjuntos)
    rec = RecordatorioCobranza.objects.create(
        factura=fac, tipo=tipo, canal=res.proveedor, destinatario=destino,
        dias_vencida=dias, saldo=saldo, ok=res.ok,
        detalle=(res.detalle or res.error or "")[:300],
    )
    _emitir_recordatorio(rec, fac, actor)
    return rec


def _emitir_recordatorio(rec: RecordatorioCobranza, fac: Factura, actor) -> None:
    emitir(EventoPortavoz(
        tipo="cobranza.recordatorio_enviado" if rec.ok else "cobranza.recordatorio_fallido",
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload={
            "factura_id": fac.id, "codigo": fac.codigo, "cliente_id": fac.cliente_id,
            "tipo": rec.tipo, "dias_vencida": rec.dias_vencida,
            "saldo": float(rec.saldo), "canal": rec.canal, "ok": rec.ok,
            "detalle": rec.detalle,
        },
    ))
