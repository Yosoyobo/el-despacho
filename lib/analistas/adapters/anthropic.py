"""Adapter Claude (Anthropic Messages API). Lee la llave desde Los Ajustes."""

from __future__ import annotations

import time

import httpx

from ..base import Adapter, ErrorPermanente, ErrorTransitorio, FaltaCredencial, Resultado
from ..capacidades import Capability

# claude-haiku-4-5: barato y rápido. Para cotizaciones largas el caller puede
# subir a sonnet pasando modelo en kwargs (S2b lo cableará).
MODELO_DEFAULT = "claude-haiku-4-5"
# Precios aproximados USD por 1M tokens (Haiku 4.5 a fecha S2a). Para reportes
# en La Sala de Juntas — son indicativos, no facturación.
PRECIO_IN = 1.00 / 1_000_000
PRECIO_OUT = 5.00 / 1_000_000


class AnthropicAdapter(Adapter):
    nombre = "anthropic"
    apodo = "Chalán Claudio"
    capacidades = frozenset({Capability.TEXTO, Capability.VISION, Capability.FUNCTION_CALLING})

    def __init__(self, modelo: str = MODELO_DEFAULT, timeout: float = 30.0):
        self.modelo = modelo
        self.timeout = timeout

    def _llave(self) -> str:
        # Import perezoso para que el adapter pueda existir sin Django arrancado.
        # Slot canónico = chalan_anthropic_api_key (pre-S2b.1); fallback al
        # slot legacy `anthropic_api_key` mientras un super_admin lo migra.
        from ajustes.models.credencial import Credencial
        llave = Credencial.obtener("chalan_anthropic_api_key") or Credencial.obtener("anthropic_api_key")
        if not llave:
            raise FaltaCredencial("chalan_anthropic_api_key no configurada en Los Ajustes")
        return llave

    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float,
                 imagenes: list | None = None) -> Resultado:
        from ..multimodal import contenido_anthropic, normalizar_imagenes
        llave = self._llave()
        imgs = normalizar_imagenes(imagenes)
        contenido = contenido_anthropic(prompt, imgs) if imgs else prompt
        t0 = time.monotonic()
        try:
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": llave,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.modelo,
                    "max_tokens": max_tokens,
                    "temperature": temperatura,
                    "messages": [{"role": "user", "content": contenido}],
                },
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ErrorTransitorio(f"anthropic: red/timeout — {exc}") from exc
        latencia = int((time.monotonic() - t0) * 1000)

        if resp.status_code == 401 or resp.status_code == 403:
            raise ErrorPermanente(f"anthropic: auth {resp.status_code}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErrorTransitorio(f"anthropic: {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ErrorPermanente(f"anthropic: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        partes = data.get("content") or []
        texto = "".join(p.get("text", "") for p in partes if p.get("type") == "text")
        usage = data.get("usage") or {}
        pt = int(usage.get("input_tokens") or 0)
        ct = int(usage.get("output_tokens") or 0)
        costo = pt * PRECIO_IN + ct * PRECIO_OUT
        return Resultado(
            texto=texto, provider=self.nombre, modelo=data.get("model") or self.modelo,
            prompt_tokens=pt, completion_tokens=ct, costo_usd=round(costo, 6),
            latencia_ms=latencia,
        )

    def consultar_saldo(self) -> dict:
        # Anthropic no expone saldo vía API pública. Link al dashboard.
        return {"soportado": False, "disponible": None, "moneda": "USD",
                "etiqueta": "Ver en dashboard",
                "fuente_url": "https://console.anthropic.com/settings/billing",
                "mensaje": "Anthropic no expone saldo vía API. Revisa el dashboard."}
