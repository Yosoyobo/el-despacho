"""Las pasarelas de La Caja — Stripe y MercadoPago, sin SDK.

Vive en `lib/` (no en la app `caja`) porque la consumen tres lados: El Taller
(los links y los webhooks), La Gerencia (Los Ajustes dice si La Caja está
encendida) y El Site (la integración aparece «no configurada» / ok). Nada de
aquí toca modelos de El Taller.

Todo es HTTP simple con `httpx`, que ya está en `requirements.txt`: no hace
falta el SDK de ninguna de las dos, y así las pruebas simulan la red cambiando
UNA función (`_pedir`).

**Encendida = llave + secreto del webhook.** Una pasarela con su llave pero sin
el secreto del webhook NO se ofrece: podría cobrar, pero el sistema nunca se
enteraría del pago (el webhook sin firma verificable se rechaza), y el cliente
pagaría una factura que seguiría apareciendo como pendiente.

**Modo prueba**: `sk_test_…` (Stripe) y `TEST-…` (MercadoPago). Funciona igual,
pero la página pública y La Caja lo avisan: nadie debe mandar a un cliente un
link que no cobra de verdad.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

logger = logging.getLogger("despacho.caja")

STRIPE_API = "https://api.stripe.com/v1"
MP_API = "https://api.mercadopago.com"
TIMEOUT = 15.0
# Stripe firma con la hora; más de 5 minutos de diferencia es un reenvío viejo
# (o un ataque de repetición). Es la tolerancia que recomienda Stripe.
TOLERANCIA_FIRMA_SEG = 300

SLOTS = {
    "stripe": ("stripe_secret_key", "stripe_webhook_secret"),
    "mercadopago": ("mercadopago_access_token", "mercadopago_webhook_secret"),
}
NOMBRES = {"stripe": "Stripe", "mercadopago": "MercadoPago"}
ETIQUETAS_SLOT = {
    "stripe_secret_key": "la llave secreta de Stripe",
    "stripe_webhook_secret": "el secreto del webhook de Stripe",
    "mercadopago_access_token": "el Access Token de MercadoPago",
    "mercadopago_webhook_secret": "el secreto del webhook de MercadoPago",
}


class ErrorPasarela(Exception):
    """La pasarela contestó mal o no contestó. El mensaje es legible."""


# ── Llaves y estado ──────────────────────────────────────────────────────────


def llaves() -> dict[str, str]:
    """Las cuatro llaves de Cobros en línea, descifradas (vacío = no puesta).

    Una sola consulta. Nunca lanza: si la base o La Bóveda fallan, todo vacío —
    y La Caja se queda apagada, que es lo seguro.
    """
    claves = [c for par in SLOTS.values() for c in par]
    salida = dict.fromkeys(claves, "")
    try:
        from ajustes.models.credencial import Credencial
        from lib.boveda import descifrar

        for fila in Credencial.objects.filter(clave__in=claves):
            try:
                salida[fila.clave] = (descifrar(fila.valor_cifrado) or "").strip()
            except Exception:  # noqa: BLE001 — una llave ilegible cuenta como vacía
                salida[fila.clave] = ""
    except Exception:  # noqa: BLE001
        logger.exception("no pude leer las llaves de La Caja")
    return salida


def _es_prueba(pasarela: str, llave: str) -> bool:
    if pasarela == "stripe":
        return llave.startswith(("sk_test_", "rk_test_"))
    return llave.startswith("TEST-")


def estado(valores: dict[str, str] | None = None) -> dict[str, Any]:
    """¿Qué pasarelas están listas para cobrar, cuáles en modo prueba, qué falta?

    ```
    {"encendida": bool, "prueba": bool, "pasarelas": ["stripe", ...],
     "stripe": {"lista", "prueba", "faltan": [slot, ...], "nombre"},
     "mercadopago": {...}}
    ```
    """
    valores = llaves() if valores is None else valores
    salida: dict[str, Any] = {"pasarelas": []}
    for pasarela, (llave, secreto) in SLOTS.items():
        faltan = [s for s in (llave, secreto) if not valores.get(s)]
        lista = not faltan
        info = {
            "nombre": NOMBRES[pasarela],
            "lista": lista,
            "prueba": lista and _es_prueba(pasarela, valores.get(llave, "")),
            "faltan": faltan,
            "faltan_texto": [ETIQUETAS_SLOT[s] for s in faltan],
            "tiene_llave": bool(valores.get(llave)),
        }
        salida[pasarela] = info
        if lista:
            salida["pasarelas"].append(pasarela)
    salida["encendida"] = bool(salida["pasarelas"])
    salida["prueba"] = any(salida[p]["prueba"] for p in salida["pasarelas"])
    return salida


def encendida() -> bool:
    """¿Hay al menos una pasarela lista? Sin esto, La Caja no ofrece nada."""
    return estado()["encendida"]


def resumen_para_ajustes() -> dict[str, str]:
    """Una línea para el grupo «Cobros en línea» de Los Ajustes: qué pasa hoy."""
    e = estado()
    if not e["encendida"]:
        partes = []
        for p in SLOTS:
            if e[p]["tiene_llave"]:
                partes.append(f"a {e[p]['nombre']} le falta {', '.join(e[p]['faltan_texto'])}")
        detalle = f" ({'; '.join(partes)})" if partes else ""
        return {
            "tono": "gris",
            "texto": ("La Caja está APAGADA y no se ve en El Taller. Con la llave y el secreto del "
                      "webhook de una pasarela se habilitan los links de pago (saldo de factura, "
                      "anticipo o monto libre), la página para que el cliente pague con tarjeta u "
                      f"OXXO/SPEI y el registro automático del cobro{detalle}."),
        }
    nombres = [e[p]["nombre"] + (" (modo prueba)" if e[p]["prueba"] else "") for p in e["pasarelas"]]
    texto = f"La Caja está ENCENDIDA con {' y '.join(nombres)}."
    if e["prueba"]:
        texto += " Con llaves de prueba los links NO cobran de verdad: la página de pago lo avisa."
    return {"tono": "ambar" if e["prueba"] else "verde", "texto": texto}


# ── HTTP ─────────────────────────────────────────────────────────────────────


def _pedir(metodo: str, url: str, **kwargs) -> tuple[int, dict]:
    """Una petición a la pasarela. `(código, json)`. Lo único que toca la red:
    las pruebas lo sustituyen y así nada sale de la máquina."""
    import httpx

    try:
        r = httpx.request(metodo, url, timeout=TIMEOUT, **kwargs)
    except httpx.HTTPError as exc:
        raise ErrorPasarela(f"No se pudo hablar con la pasarela: {exc}"[:200]) from exc
    try:
        cuerpo = r.json()
    except ValueError:
        cuerpo = {}
    return r.status_code, cuerpo if isinstance(cuerpo, dict) else {"_lista": cuerpo}


def _error_de(cuerpo: dict, codigo: int) -> str:
    err = cuerpo.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err.get("type") or codigo)[:200]
    return str(cuerpo.get("message") or err or f"HTTP {codigo}")[:200]


def centavos(monto) -> int:
    """$1,234.50 → 123450. Stripe cobra en la unidad mínima de la moneda."""
    return int((Decimal(str(monto)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ── Stripe ───────────────────────────────────────────────────────────────────


def stripe_crear_checkout(*, monto, concepto: str, referencia: str, link_id: int,
                          url_exito: str, url_cancelado: str, email: str = "") -> dict:
    """Crea una Checkout Session (pago único con tarjeta). `{id, url, expira}`."""
    llave = llaves()["stripe_secret_key"]
    if not llave:
        raise ErrorPasarela("Stripe no está configurado.")
    datos = {
        "mode": "payment",
        "line_items[0][price_data][currency]": "mxn",
        "line_items[0][price_data][unit_amount]": str(centavos(monto)),
        "line_items[0][price_data][product_data][name]": (concepto or "Pago")[:250],
        "line_items[0][quantity]": "1",
        "payment_method_types[0]": "card",
        "success_url": url_exito,
        "cancel_url": url_cancelado,
        "client_reference_id": referencia,
        "metadata[link_id]": str(link_id),
        "metadata[referencia]": referencia,
        "payment_intent_data[metadata][link_id]": str(link_id),
        "payment_intent_data[metadata][referencia]": referencia,
        "locale": "es-419",
    }
    if email:
        datos["customer_email"] = email
    codigo, cuerpo = _pedir(
        "POST", f"{STRIPE_API}/checkout/sessions",
        headers={"Authorization": f"Bearer {llave}", "Idempotency-Key": uuid.uuid4().hex},
        data=datos,
    )
    if codigo != 200 or not cuerpo.get("url"):
        raise ErrorPasarela(f"Stripe no creó el cobro: {_error_de(cuerpo, codigo)}")
    return {"id": cuerpo.get("id", ""), "url": cuerpo["url"], "expira": cuerpo.get("expires_at")}


def stripe_expirar(sesion_id: str) -> bool:
    """Cierra una Checkout Session abierta (al anular su link). Best-effort."""
    if not sesion_id:
        return False
    llave = llaves()["stripe_secret_key"]
    if not llave:
        return False
    try:
        codigo, _ = _pedir("POST", f"{STRIPE_API}/checkout/sessions/{sesion_id}/expire",
                           headers={"Authorization": f"Bearer {llave}"})
    except ErrorPasarela:
        return False
    return codigo == 200


def stripe_firma_valida(cuerpo: bytes, cabecera: str, secreto: str, *,
                        ahora: int | None = None) -> bool:
    """Verifica `Stripe-Signature` (`t=…,v1=…`): HMAC-SHA256 de `t.cuerpo` con el
    secreto del webhook, dentro de la tolerancia de tiempo. Sin secreto, NO."""
    if not (cuerpo is not None and cabecera and secreto):
        return False
    marca = ""
    firmas: list[str] = []
    for parte in cabecera.split(","):
        clave, _, valor = parte.strip().partition("=")
        if clave == "t":
            marca = valor
        elif clave == "v1":
            firmas.append(valor)
    if not marca.isdigit() or not firmas:
        return False
    ahora = int(time.time()) if ahora is None else ahora
    if abs(ahora - int(marca)) > TOLERANCIA_FIRMA_SEG:
        return False
    esperada = hmac.new(secreto.encode(), marca.encode() + b"." + cuerpo, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(esperada, f) for f in firmas)


def probar_stripe() -> dict[str, Any]:
    """Para El Site: ¿la llave sirve? Lee el saldo (no cobra ni crea nada)."""
    e = estado()["stripe"]
    if not e["tiene_llave"]:
        return {"estado": "no_configurada", "mensaje_error": "stripe_secret_key no configurada"}
    t0 = time.monotonic()
    try:
        codigo, cuerpo = _pedir("GET", f"{STRIPE_API}/balance",
                                headers={"Authorization": f"Bearer {llaves()['stripe_secret_key']}"})
    except ErrorPasarela as exc:
        return {"estado": "error", "mensaje_error": str(exc), "latencia_ms": int((time.monotonic() - t0) * 1000)}
    latencia = int((time.monotonic() - t0) * 1000)
    if codigo != 200:
        return {"estado": "error", "mensaje_error": _error_de(cuerpo, codigo), "latencia_ms": latencia}
    if not e["lista"]:
        return {"estado": "error", "latencia_ms": latencia,
                "mensaje_error": "La llave sirve, pero falta el secreto del webhook: La Caja no la ofrece."}
    return {"estado": "ok", "latencia_ms": latencia}


# ── MercadoPago ──────────────────────────────────────────────────────────────


def mp_crear_preferencia(*, monto, concepto: str, referencia: str, link_id: int,
                         url_exito: str, url_cancelado: str, vence_en=None) -> dict:
    """Preferencia de Checkout Pro (tarjeta, OXXO, SPEI, saldo MP). `{id, url}`."""
    token = llaves()["mercadopago_access_token"]
    if not token:
        raise ErrorPasarela("MercadoPago no está configurado.")
    cuerpo_pref: dict[str, Any] = {
        "items": [{
            "id": f"link-{link_id}",
            "title": (concepto or "Pago")[:250],
            "quantity": 1,
            "unit_price": float(Decimal(str(monto)).quantize(Decimal("0.01"))),
            "currency_id": "MXN",
        }],
        "external_reference": referencia,
        "metadata": {"link_id": link_id},
        "back_urls": {"success": url_exito, "pending": url_exito, "failure": url_cancelado},
        "auto_return": "approved",
    }
    if vence_en is not None:
        cuerpo_pref["expires"] = True
        cuerpo_pref["expiration_date_to"] = vence_en.isoformat(timespec="milliseconds")
    codigo, cuerpo = _pedir(
        "POST", f"{MP_API}/checkout/preferences",
        headers={"Authorization": f"Bearer {token}", "X-Idempotency-Key": uuid.uuid4().hex},
        json=cuerpo_pref,
    )
    if codigo not in (200, 201) or not cuerpo.get("init_point"):
        raise ErrorPasarela(f"MercadoPago no creó el cobro: {_error_de(cuerpo, codigo)}")
    url = cuerpo["init_point"]
    if _es_prueba("mercadopago", token) and cuerpo.get("sandbox_init_point"):
        url = cuerpo["sandbox_init_point"]
    return {"id": cuerpo.get("id", ""), "url": url}


def mp_expirar(preferencia_id: str) -> bool:
    """Vence una preferencia ya (al anular su link). Best-effort."""
    if not preferencia_id:
        return False
    token = llaves()["mercadopago_access_token"]
    if not token:
        return False
    from django.utils import timezone
    try:
        codigo, _ = _pedir(
            "PUT", f"{MP_API}/checkout/preferences/{preferencia_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"expires": True,
                  "expiration_date_to": timezone.now().isoformat(timespec="milliseconds")},
        )
    except ErrorPasarela:
        return False
    return codigo == 200


def mp_firma_valida(*, cabecera: str, request_id: str, data_id: str, secreto: str) -> bool:
    """Verifica `x-signature` (`ts=…,v1=…`) de MercadoPago.

    El manifiesto es `id:<data.id>;request-id:<x-request-id>;ts:<ts>;` (se omite
    la parte que no venga) firmado con HMAC-SHA256 y el secreto del webhook. El
    `data.id` alfanumérico va en minúsculas — así lo firma MercadoPago.
    """
    if not (cabecera and secreto):
        return False
    marca, firma = "", ""
    for parte in cabecera.split(","):
        clave, _, valor = parte.strip().partition("=")
        if clave == "ts":
            marca = valor.strip()
        elif clave == "v1":
            firma = valor.strip()
    if not marca or not firma:
        return False
    manifiesto = ""
    if data_id:
        manifiesto += f"id:{data_id.lower() if data_id.isalnum() else data_id};"
    if request_id:
        manifiesto += f"request-id:{request_id};"
    manifiesto += f"ts:{marca};"
    esperada = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma)


def mp_consultar_pago(pago_id: str) -> dict:
    """El pago tal como lo tiene MercadoPago. El aviso del webhook sólo trae el
    id: el monto y el estado se le creen a la API, no al aviso."""
    token = llaves()["mercadopago_access_token"]
    if not token:
        raise ErrorPasarela("MercadoPago no está configurado.")
    codigo, cuerpo = _pedir("GET", f"{MP_API}/v1/payments/{pago_id}",
                            headers={"Authorization": f"Bearer {token}"})
    if codigo != 200:
        raise ErrorPasarela(f"MercadoPago no devolvió el pago {pago_id}: {_error_de(cuerpo, codigo)}")
    return cuerpo


def probar_mercadopago() -> dict[str, Any]:
    """Para El Site: ¿el token sirve? Lee la cuenta (no cobra ni crea nada)."""
    e = estado()["mercadopago"]
    if not e["tiene_llave"]:
        return {"estado": "no_configurada", "mensaje_error": "mercadopago_access_token no configurado"}
    t0 = time.monotonic()
    try:
        codigo, cuerpo = _pedir("GET", f"{MP_API}/users/me",
                                headers={"Authorization": f"Bearer {llaves()['mercadopago_access_token']}"})
    except ErrorPasarela as exc:
        return {"estado": "error", "mensaje_error": str(exc), "latencia_ms": int((time.monotonic() - t0) * 1000)}
    latencia = int((time.monotonic() - t0) * 1000)
    if codigo != 200:
        return {"estado": "error", "mensaje_error": _error_de(cuerpo, codigo), "latencia_ms": latencia}
    if not e["lista"]:
        return {"estado": "error", "latencia_ms": latencia,
                "mensaje_error": "El token sirve, pero falta el secreto del webhook: La Caja no lo ofrece."}
    return {"estado": "ok", "latencia_ms": latencia}
