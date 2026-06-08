"""Chalán Gemini — adapter Google Generative Language API.

Activado en S-Demo-Pre-Showcase (2026-05-24). Llama a
`v1beta/models/<modelo>:generateContent?key=<API_KEY>`.

API key se pega como query string `?key=` (estándar Google), NO en header
de auth. Esquema de request/response distinto al estilo OpenAI:

  Request body:
    {
      "contents": [{"parts": [{"text": "..."}]}],
      "generationConfig": {"maxOutputTokens": N, "temperature": F}
    }

  Response:
    {
      "candidates": [{"content": {"parts": [{"text": "..."}]}, ...}],
      "usageMetadata": {"promptTokenCount": N, "candidatesTokenCount": M,
                         "totalTokenCount": N+M}
    }

Modelo default: `gemini-2.5-flash` (barato y rápido). Cambiar a
`gemini-2.5-pro` si LC quiere razonamiento más fuerte. Precio
placeholder $0/$0 — Oscar confirma con consola Google y actualiza.
"""

from __future__ import annotations

import time

import httpx

from ..base import Adapter, ErrorPermanente, ErrorTransitorio, FaltaCredencial, Resultado
from ..capacidades import Capability

MODELO_DEFAULT = "gemini-2.5-flash"
API_URL_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# gemini-2.5-flash · tarifa oficial Google AI Studio (Mayo 2026):
#   $0.30 / MTok input  ·  $2.50 / MTok output
# Si cambias a gemini-2.5-pro, ajusta a 1.25 in / 10.00 out.
PRECIO_IN = 0.30 / 1_000_000
PRECIO_OUT = 2.50 / 1_000_000


class GeminiAdapter(Adapter):
    nombre = "gemini"
    apodo = "Chalán Gemini"
    capacidades = frozenset({Capability.TEXTO, Capability.VISION, Capability.FUNCTION_CALLING})

    def __init__(self, modelo: str = MODELO_DEFAULT, timeout: float = 30.0):
        self.modelo = modelo
        self.timeout = timeout

    def _llave(self) -> str:
        from ajustes.models.credencial import Credencial
        llave = Credencial.obtener("chalan_gemini_api_key")
        if not llave:
            raise FaltaCredencial("chalan_gemini_api_key no configurada en Los Ajustes")
        return llave

    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float,
                 imagenes: list | None = None) -> Resultado:
        from ..multimodal import normalizar_imagenes, partes_gemini
        llave = self._llave()
        imgs = normalizar_imagenes(imagenes)
        partes = partes_gemini(prompt, imgs) if imgs else [{"text": prompt}]
        url = f"{API_URL_BASE}/{self.modelo}:generateContent"
        t0 = time.monotonic()
        try:
            resp = httpx.post(
                url,
                params={"key": llave},
                headers={"content-type": "application/json"},
                json={
                    "contents": [{"parts": partes}],
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": temperatura,
                    },
                },
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ErrorTransitorio(f"gemini: red/timeout — {exc}") from exc
        latencia = int((time.monotonic() - t0) * 1000)

        if resp.status_code in (401, 403):
            raise ErrorPermanente(f"gemini: auth {resp.status_code}")
        if resp.status_code == 400:
            raise ErrorPermanente(f"gemini: 400 {resp.text[:200]}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErrorTransitorio(f"gemini: {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ErrorPermanente(f"gemini: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        candidates = data.get("candidates") or []
        texto = ""
        if candidates:
            partes = (candidates[0].get("content") or {}).get("parts") or []
            texto = "".join(p.get("text", "") for p in partes)
        usage = data.get("usageMetadata") or {}
        pt = int(usage.get("promptTokenCount") or 0)
        ct = int(usage.get("candidatesTokenCount") or 0)
        costo = pt * PRECIO_IN + ct * PRECIO_OUT
        return Resultado(
            texto=texto, provider=self.nombre, modelo=self.modelo,
            prompt_tokens=pt, completion_tokens=ct, costo_usd=round(costo, 6),
            latencia_ms=latencia,
        )

    def consultar_saldo(self) -> dict:
        # Google no expone API pública de saldo del API key. Link a consola.
        return {
            "soportado": False, "disponible": None, "moneda": "USD",
            "etiqueta": "Consulta consola",
            "fuente_url": "https://aistudio.google.com/app/apikey",
            "mensaje": "Google no expone saldo por API. Revisa AI Studio.",
        }
