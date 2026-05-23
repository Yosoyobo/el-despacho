"""Chalán MiMo — adapter MiMo de Xiaomi (API tipo OpenAI con 3 diferencias).

Diferencias clave vs OpenAI/Deepseek:
  - Base URL: https://api.xiaomimimo.com/v1
  - Header de auth: `api-key: <KEY>` (NO `Authorization: Bearer`)
  - Parámetro de límite: `max_completion_tokens` (NO `max_tokens`)
  - Soporta visión (`mimo-v2.5-pro`).

Docs: https://platform.xiaomimimo.com/docs/en-US/quick-start/first-api-call
"""

from __future__ import annotations

import time

import httpx

from ..base import Adapter, ErrorPermanente, ErrorTransitorio, FaltaCredencial, Resultado
from ..capacidades import Capability

MODELO_DEFAULT = "mimo-v2.5-pro"
API_URL = "https://api.xiaomimimo.com/v1/chat/completions"

# MiMo (Xiaomi) está actualmente en programa de acceso gratuito — no se
# cobra por uso. Precios = 0 hasta que Xiaomi publique tarifa oficial.
# Cuando dejen de ser gratis, actualizar a valores reales y emitir un
# evento "chalan.precio_actualizado" para que la UI alerte al admin.
PRECIO_IN = 0.0
PRECIO_OUT = 0.0


class MimoAdapter(Adapter):
    nombre = "mimo"
    apodo = "Chalán MiMo"
    capacidades = frozenset({Capability.TEXTO, Capability.VISION, Capability.FUNCTION_CALLING})

    def __init__(self, modelo: str = MODELO_DEFAULT, timeout: float = 30.0):
        self.modelo = modelo
        self.timeout = timeout

    def _llave(self) -> str:
        from ajustes.models.credencial import Credencial
        llave = Credencial.obtener("chalan_mimo_api_key")
        if not llave:
            raise FaltaCredencial("chalan_mimo_api_key no configurada en Los Ajustes")
        return llave

    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float) -> Resultado:
        llave = self._llave()
        t0 = time.monotonic()
        try:
            resp = httpx.post(
                API_URL,
                headers={
                    "api-key": llave,
                    "content-type": "application/json",
                },
                json={
                    "model": self.modelo,
                    "max_completion_tokens": max_tokens,
                    "temperature": temperatura,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ErrorTransitorio(f"mimo: red/timeout — {exc}") from exc
        latencia = int((time.monotonic() - t0) * 1000)

        if resp.status_code in (401, 403):
            raise ErrorPermanente(f"mimo: auth {resp.status_code}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErrorTransitorio(f"mimo: {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ErrorPermanente(f"mimo: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        choices = data.get("choices") or []
        texto = (choices[0].get("message", {}).get("content") if choices else "") or ""
        usage = data.get("usage") or {}
        pt = int(usage.get("prompt_tokens") or 0)
        ct = int(usage.get("completion_tokens") or 0)
        costo = pt * PRECIO_IN + ct * PRECIO_OUT
        return Resultado(
            texto=texto, provider=self.nombre, modelo=data.get("model") or self.modelo,
            prompt_tokens=pt, completion_tokens=ct, costo_usd=round(costo, 6),
            latencia_ms=latencia,
        )

    def consultar_saldo(self) -> dict:
        # MiMo (Xiaomi) está en programa gratuito en este momento.
        return {"soportado": True, "disponible": None, "moneda": "USD",
                "etiqueta": "Gratis (programa de acceso)",
                "fuente_url": "https://www.xiaomimimo.com/",
                "mensaje": "MiMo está actualmente sin costo por uso. Revisa periódicamente."}
