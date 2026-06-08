"""Adapter OpenAI (Chat Completions). Fallback de Anthropic."""

from __future__ import annotations

import time

import httpx

from ..base import Adapter, ErrorPermanente, ErrorTransitorio, FaltaCredencial, Resultado
from ..capacidades import Capability

MODELO_DEFAULT = "gpt-4o-mini"
PRECIO_IN = 0.15 / 1_000_000
PRECIO_OUT = 0.60 / 1_000_000


class OpenAIAdapter(Adapter):
    nombre = "openai"
    apodo = "Chalán GPT"
    capacidades = frozenset({Capability.TEXTO, Capability.VISION, Capability.FUNCTION_CALLING})

    def __init__(self, modelo: str = MODELO_DEFAULT, timeout: float = 30.0):
        self.modelo = modelo
        self.timeout = timeout

    def _llave(self) -> str:
        from ajustes.models.credencial import Credencial
        llave = Credencial.obtener("chalan_openai_api_key") or Credencial.obtener("openai_api_key")
        if not llave:
            raise FaltaCredencial("chalan_openai_api_key no configurada en Los Ajustes")
        return llave

    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float,
                 imagenes: list | None = None) -> Resultado:
        from ..multimodal import contenido_openai, normalizar_imagenes
        llave = self._llave()
        imgs = normalizar_imagenes(imagenes)
        contenido = contenido_openai(prompt, imgs) if imgs else prompt
        t0 = time.monotonic()
        try:
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {llave}", "content-type": "application/json"},
                json={
                    "model": self.modelo,
                    "max_tokens": max_tokens,
                    "temperature": temperatura,
                    "messages": [{"role": "user", "content": contenido}],
                },
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ErrorTransitorio(f"openai: red/timeout — {exc}") from exc
        latencia = int((time.monotonic() - t0) * 1000)

        if resp.status_code == 401 or resp.status_code == 403:
            raise ErrorPermanente(f"openai: auth {resp.status_code}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErrorTransitorio(f"openai: {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ErrorPermanente(f"openai: {resp.status_code} {resp.text[:200]}")

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
        # OpenAI deprecó `/v1/dashboard/billing/credit_grants`. Link al dashboard.
        return {"soportado": False, "disponible": None, "moneda": "USD",
                "etiqueta": "Ver en dashboard",
                "fuente_url": "https://platform.openai.com/settings/organization/billing/overview",
                "mensaje": "OpenAI no expone saldo vía API. Revisa el dashboard."}
