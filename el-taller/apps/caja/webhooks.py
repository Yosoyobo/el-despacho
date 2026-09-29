"""Webhooks de La Caja — la pasarela avisa que el cliente pagó.

Reglas que no se relajan:

  · **Firma obligatoria.** Sin firma válida no se lee nada: Stripe con
    `Stripe-Signature` + `stripe_webhook_secret`; MercadoPago con `x-signature`
    + `mercadopago_webhook_secret`. Sin llaves, el extremo ni existe (404).
  · **MercadoPago se consulta a su API** antes de creerle: el aviso sólo trae
    un id; el monto y el estado se leen de `/v1/payments/<id>`.
  · **Idempotentes.** Las dos pasarelas repiten avisos; `services.recibir_pago`
    guarda una fila por pago y el segundo aviso no crea otro ingreso.
  · **Sin CSRF** (los manda un servidor, no un navegador) — la firma es la
    protección, y por eso se verifica ANTES de tocar el cuerpo.
  · Un evento de PRUEBA con llaves REALES se ignora (y al revés): un webhook
    mal configurado no mete dinero de mentiras a la contabilidad.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from lib import pasarelas

from . import services

logger = logging.getLogger("despacho.caja")

EVENTOS_STRIPE = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
}
PENDIENTES_MP = {"pending", "in_process", "authorized", "in_mediation"}


def _ok(**extra) -> JsonResponse:
    return JsonResponse({"ok": True, **extra})


@csrf_exempt
@require_POST
def webhook_stripe(request):
    llaves = pasarelas.llaves()
    secreto = llaves["stripe_webhook_secret"]
    if not (llaves["stripe_secret_key"] and secreto):
        return HttpResponse(status=404)
    if not pasarelas.stripe_firma_valida(request.body, request.headers.get("Stripe-Signature", ""), secreto):
        logger.warning("caja: webhook de Stripe con firma inválida")
        return HttpResponse("firma inválida", status=400)
    try:
        evento = json.loads(request.body)
    except ValueError:
        return HttpResponse("cuerpo inválido", status=400)
    tipo = evento.get("type", "")
    if tipo not in EVENTOS_STRIPE:
        return _ok(ignorado=tipo)
    prueba = pasarelas.estado(llaves)["stripe"]["prueba"]
    if bool(evento.get("livemode")) == prueba:
        return _ok(ignorado="modo distinto al de la llave")
    sesion = (evento.get("data") or {}).get("object") or {}
    metadata = sesion.get("metadata") or {}
    pagado = sesion.get("payment_status") == "paid" and tipo != "checkout.session.async_payment_failed"
    try:
        monto = Decimal(int(sesion.get("amount_total") or 0)) / 100
        creado = datetime.fromtimestamp(int(evento.get("created") or 0), tz=UTC) if evento.get("created") else None
        services.recibir_pago(
            pasarela="stripe",
            id_externo=sesion.get("payment_intent") or sesion.get("id") or "",
            monto=monto,
            moneda=sesion.get("currency") or "",
            estado_pasarela=sesion.get("payment_status") or "",
            aprobado=pagado,
            pendiente=(tipo == "checkout.session.completed" and sesion.get("payment_status") == "unpaid"),
            referencia=sesion.get("client_reference_id") or metadata.get("referencia") or "",
            fecha_pago=creado,
            payload={
                "evento_id": evento.get("id"), "evento_tipo": tipo, "sesion_id": sesion.get("id"),
                "payment_intent": sesion.get("payment_intent"), "estado": sesion.get("payment_status"),
                "monto": str(monto), "moneda": sesion.get("currency"),
                "referencia": sesion.get("client_reference_id"),
            },
        )
    except (ValueError, TypeError, InvalidOperation) as exc:
        logger.warning("caja: aviso de Stripe inservible: %s", exc)
        return HttpResponse("aviso inválido", status=400)
    except Exception:  # noqa: BLE001 — 500 = Stripe reintenta; el dinero no se pierde
        logger.exception("caja: falló el webhook de Stripe")
        return HttpResponse(status=500)
    return _ok()


def _cuerpo_json(request) -> dict:
    try:
        cuerpo = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    return cuerpo if isinstance(cuerpo, dict) else {}


@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    llaves = pasarelas.llaves()
    secreto = llaves["mercadopago_webhook_secret"]
    if not (llaves["mercadopago_access_token"] and secreto):
        return HttpResponse(status=404)
    cuerpo = _cuerpo_json(request)
    # MercadoPago firma el `data.id` de la URL; el del cuerpo es el respaldo.
    data_id = (request.GET.get("data.id") or str((cuerpo.get("data") or {}).get("id") or "")).strip()
    if not pasarelas.mp_firma_valida(
        cabecera=request.headers.get("x-signature", ""),
        request_id=request.headers.get("x-request-id", ""),
        data_id=data_id, secreto=secreto,
    ):
        logger.warning("caja: webhook de MercadoPago con firma inválida")
        return HttpResponse("firma inválida", status=401)
    tipo = request.GET.get("type") or cuerpo.get("type") or cuerpo.get("topic") or ""
    if tipo != "payment" or not data_id:
        return _ok(ignorado=tipo)
    try:
        pago = pasarelas.mp_consultar_pago(data_id)
    except pasarelas.ErrorPasarela as exc:
        logger.warning("caja: MercadoPago no confirmó el pago %s: %s", data_id, exc)
        return HttpResponse(status=502)  # MercadoPago reintenta
    prueba = pasarelas.estado(llaves)["mercadopago"]["prueba"]
    if "live_mode" in pago and bool(pago.get("live_mode")) == prueba:
        return _ok(ignorado="modo distinto al de la llave")
    estado = str(pago.get("status") or "")
    fecha = parse_datetime(str(pago.get("date_approved") or pago.get("date_created") or ""))
    try:
        services.recibir_pago(
            pasarela="mercadopago",
            id_externo=str(pago.get("id") or data_id),
            monto=pago.get("transaction_amount") or 0,
            moneda=pago.get("currency_id") or "",
            estado_pasarela=estado,
            aprobado=estado == "approved",
            pendiente=estado in PENDIENTES_MP,
            referencia=str(pago.get("external_reference") or ""),
            fecha_pago=fecha,
            payload={
                "pago_id": pago.get("id"), "estado": estado, "estado_detalle": pago.get("status_detail"),
                "monto": str(pago.get("transaction_amount")), "moneda": pago.get("currency_id"),
                "metodo": pago.get("payment_method_id"), "tipo_metodo": pago.get("payment_type_id"),
                "referencia": pago.get("external_reference"),
            },
        )
    except (ValueError, TypeError, InvalidOperation) as exc:
        logger.warning("caja: aviso de MercadoPago inservible: %s", exc)
        return HttpResponse("aviso inválido", status=400)
    except Exception:  # noqa: BLE001
        logger.exception("caja: falló el webhook de MercadoPago")
        return HttpResponse(status=500)
    return _ok()
