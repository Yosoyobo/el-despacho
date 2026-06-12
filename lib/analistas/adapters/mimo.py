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

# MiMo (Xiaomi) salió del programa gratuito. Tarifa por token (USD/token).
# NOTA: placeholder marcado — confirmar con Xiaomi la tarifa oficial. El conteo
# de tokens y llamadas (AnalistaLog) es exacto sin importar el precio; solo el
# costo estimado depende de estos valores. Ajustar cuando se publique la tarifa.
PRECIO_IN = 0.30 / 1_000_000   # placeholder — confirmar con Xiaomi
PRECIO_OUT = 0.60 / 1_000_000  # placeholder — confirmar con Xiaomi
MODELOS_CURADOS = ("mimo-v2.5-pro", "mimo-v2.5")


class MimoAdapter(Adapter):
    nombre = "mimo"
    apodo = "Chalán MiMo"
    capacidades = frozenset({Capability.TEXTO, Capability.VISION, Capability.FUNCTION_CALLING})
    modelo_default = MODELO_DEFAULT
    modelos_curados = MODELOS_CURADOS

    def __init__(self, modelo: str = MODELO_DEFAULT, timeout: float = 30.0):
        self.modelo = modelo
        self.timeout = timeout

    def _llave(self) -> str:
        from ajustes.models.credencial import Credencial
        llave = Credencial.obtener("chalan_mimo_api_key")
        if not llave:
            raise FaltaCredencial("chalan_mimo_api_key no configurada en Los Ajustes")
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
                API_URL,
                headers={
                    "api-key": llave,
                    "content-type": "application/json",
                },
                json={
                    "model": self.modelo,
                    "max_completion_tokens": max_tokens,
                    "temperature": temperatura,
                    "messages": [{"role": "user", "content": contenido}],
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

    def listar_modelos(self) -> list[str]:
        try:
            llave = self._llave()
        except Exception:
            return list(MODELOS_CURADOS)
        try:
            resp = httpx.get(
                "https://api.xiaomimimo.com/v1/models",
                headers={"api-key": llave},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return list(MODELOS_CURADOS)
            ids = [m.get("id") for m in (resp.json().get("data") or []) if m.get("id")]
            return ids or list(MODELOS_CURADOS)
        except Exception:
            return list(MODELOS_CURADOS)

    def consultar_saldo(self) -> dict:
        """MiMo no documenta un endpoint público de saldo. Reportamos
        `soportado=False` y la UI muestra el uso (llamadas/tokens/costo) que
        ya viene de `AnalistaLog`. Si Xiaomi publica un endpoint de balance,
        implementarlo aquí estilo Deepseek (`GET /user/balance`)."""
        return {"soportado": False, "disponible": None, "moneda": "USD",
                "etiqueta": "—",
                "fuente_url": "https://platform.xiaomimimo.com/",
                "mensaje": "MiMo no expone saldo por API; revisa el uso (llamadas, tokens y costo)."}
