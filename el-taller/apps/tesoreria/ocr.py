"""OCR de comprobantes (S-Chalán-Scope-OCR, fase C3).

Sube la foto/PDF de un recibo a un Chalán con visión (estación `ocr_recibo`,
cadena con fallback) y extrae monto/fecha/proveedor/concepto. NO crea el
Egreso: pre-llena el form para que el usuario revise/edite/guarde (decisión
Oscar 2026-06-07). Cada corrida queda registrada en `EgresoOcrLog`.

Diseño defensivo: nunca lanza hacia el caller — devuelve un dict
`{ok, datos, log_id, chalan, error}`. Si no hay Chalán con visión configurado,
o el LLM cae, o el JSON viene mal, retorna `ok=False` con un mensaje claro.
"""

from __future__ import annotations

import base64
import json
import re
from decimal import Decimal, InvalidOperation

_PROMPT = (
    "Eres un asistente de captura contable. Te doy la imagen de un recibo, "
    "ticket o factura simple mexicana. Extrae SOLO estos campos y responde en "
    "JSON ESTRICTO, sin texto fuera del JSON:\n"
    '{\n'
    '  "total": número (monto total a pagar, con IVA si aplica) o null,\n'
    '  "subtotal": número (antes de IVA) o null,\n'
    '  "iva": número (importe de IVA) o null,\n'
    '  "fecha": "YYYY-MM-DD" o null,\n'
    '  "proveedor": "nombre del comercio/proveedor" o null,\n'
    '  "concepto": "descripción breve de lo comprado" o null,\n'
    '  "moneda": "MXN"|"USD" o null\n'
    "}\n"
    "Si un dato no está claro, usa null. No inventes. No expliques."
)

# Tope de salida del LLM — la respuesta es un JSON chico.
_MAX_TOKENS = 400


def _a_decimal(valor):
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor).replace(",", "").replace("$", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parsear_json(texto: str) -> dict | None:
    """Extrae el primer objeto JSON del texto (tolera ```json fences)."""
    if not texto:
        return None
    limpio = texto.strip()
    limpio = re.sub(r"^```(?:json)?", "", limpio).strip()
    limpio = re.sub(r"```$", "", limpio).strip()
    m = re.search(r"\{.*\}", limpio, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _normalizar(crudo: dict) -> dict:
    """Crudo del LLM → dict listo para pre-llenar el form de Egreso."""
    fecha = (crudo.get("fecha") or "").strip()[:10] or None
    if fecha and not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha):
        fecha = None
    total = _a_decimal(crudo.get("total"))
    subtotal = _a_decimal(crudo.get("subtotal"))
    iva = _a_decimal(crudo.get("iva"))
    # El form de Egreso captura `subtotal` y deriva el total (×1.16 si IVA).
    # Si el recibo trae subtotal explícito + IVA, usamos subtotal e incluye_iva;
    # si solo trae total, lo ponemos como subtotal sin IVA (el usuario ajusta).
    if subtotal and iva:
        sugerido_subtotal, incluye_iva = subtotal, True
    else:
        sugerido_subtotal, incluye_iva = (total or subtotal), False
    moneda = (crudo.get("moneda") or "MXN").upper()
    if moneda not in {"MXN", "USD"}:
        moneda = "MXN"
    return {
        "total": float(total) if total else None,
        "subtotal_sugerido": float(sugerido_subtotal) if sugerido_subtotal else None,
        "incluye_iva": incluye_iva,
        "fecha": fecha,
        "proveedor": (crudo.get("proveedor") or "").strip()[:200] or None,
        "concepto": (crudo.get("concepto") or "").strip()[:300] or None,
        "moneda": moneda,
    }


def extraer_recibo(
    *,
    contenido: bytes,
    media_type: str,
    nombre_original: str = "",
    usuario=None,
    drive_file_id: str = "",
    tamano_original: int = 0,
) -> dict:
    """Corre el OCR sobre `contenido`. Devuelve `{ok, datos, log_id, chalan, error}`.

    Registra SIEMPRE un `EgresoOcrLog` (incluso en fallo) para trazabilidad.
    `datos` (cuando ok) ya viene normalizado para el form de Egreso.
    """
    from .models import EgresoOcrLog

    b64 = base64.b64encode(contenido).decode("ascii")
    imagenes = [{"base64": b64, "media_type": (media_type or "image/jpeg").lower()}]

    chalan = ""
    modelo = ""
    latencia = 0
    costo = Decimal("0")
    crudo: dict | None = None
    error = ""

    try:
        from chalanes.voz import preludio, reglas
        from lib.analistas import analizar
        res = analizar(
            estacion="ocr_recibo", prompt=preludio("ocr_recibo") + _PROMPT + reglas(), imagenes=imagenes,
            max_tokens=_MAX_TOKENS, temperatura=0.0,
            actor_id=getattr(usuario, "pk", None),
        )
        chalan, modelo, latencia = res.provider, res.modelo, res.latencia_ms
        costo = Decimal(str(res.costo_usd))
        crudo = _parsear_json(res.texto)
        if crudo is None:
            error = "El Chalán no devolvió un JSON legible del recibo."
    except Exception as exc:  # noqa: BLE001 — el OCR nunca tumba la pantalla
        error = f"No se pudo leer el recibo: {str(exc)[:200]}"

    log = EgresoOcrLog.objects.create(
        drive_file_id=drive_file_id,
        nombre_original=(nombre_original or "")[:300],
        tamano_original_bytes=tamano_original or len(contenido),
        mime_type=(media_type or "")[:100],
        chalan_usado=(chalan or "")[:30],
        modelo=(modelo or "")[:80],
        raw_extraccion=crudo or {},
        latencia_ms=latencia,
        costo_usd=costo,
        creado_por=usuario if getattr(usuario, "pk", None) else None,
    )

    if crudo is None:
        return {"ok": False, "datos": None, "log_id": log.pk, "chalan": chalan,
                "error": error or "No se pudo extraer la información."}

    return {"ok": True, "datos": _normalizar(crudo), "log_id": log.pk,
            "chalan": chalan, "error": ""}
