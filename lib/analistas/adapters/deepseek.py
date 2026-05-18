"""Chalán Chino — adapter Deepseek (API compatible OpenAI).

NO soporta visión. Si se le pasa una imagen, lanza SinCapacidad y El
Reemplazo salta al siguiente Chalán de la cadena.
"""

from __future__ import annotations

import time

import httpx

from ..base import Adapter, ErrorPermanente, ErrorTransitorio, FaltaCredencial, Resultado
from ..capacidades import Capability

MODELO_DEFAULT = "deepseek-chat"
# Precios aproximados USD por 1M tokens (deepseek-chat a fecha pre-S2b.1).
PRECIO_IN = 0.14 / 1_000_000
PRECIO_OUT = 0.28 / 1_000_000


class DeepseekAdapter(Adapter):
    nombre = "deepseek"
    apodo = "Chalán Chino"
    capacidades = frozenset({Capability.TEXTO, Capability.FUNCTION_CALLING})

    def __init__(self, modelo: str = MODELO_DEFAULT, timeout: float = 30.0):
        self.modelo = modelo
        self.timeout = timeout

    def _llave(self) -> str:
        from ajustes.models.credencial import Credencial
        llave = Credencial.obtener("chalan_deepseek_api_key")
        if not llave:
            raise FaltaCredencial("chalan_deepseek_api_key no configurada en Los Ajustes")
        return llave

    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float) -> Resultado:
        llave = self._llave()
        t0 = time.monotonic()
        try:
            resp = httpx.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {llave}",
                    "content-type": "application/json",
                },
                json={
                    "model": self.modelo,
                    "max_tokens": max_tokens,
                    "temperature": temperatura,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ErrorTransitorio(f"deepseek: red/timeout — {exc}") from exc
        latencia = int((time.monotonic() - t0) * 1000)

        if resp.status_code in (401, 403):
            raise ErrorPermanente(f"deepseek: auth {resp.status_code}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErrorTransitorio(f"deepseek: {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ErrorPermanente(f"deepseek: {resp.status_code} {resp.text[:200]}")

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
