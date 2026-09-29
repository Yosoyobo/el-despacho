"""Chalán Grok — adapter Grok de xAI (API compatible con OpenAI).

xAI expone un endpoint compatible con OpenAI en
`https://api.x.ai/v1/chat/completions` (Bearer auth, `max_tokens`, formato
`messages`/`choices`), así que reutiliza toda la plomería OpenAI del repo
(multimodal `contenido_openai`, `herramientas_formato`). Es cloud estándar:
la API key se pega en Los Ajustes (slot `chalan_grok_api_key`) igual que los
demás Chalanes cloud, y entra solo a la cadena de fallback al guardar la llave
(vía el signal `auto_agregar_a_cadena_fallback`).

Nota: xAI también publica el endpoint más nuevo `/v1/responses`, pero El
Despacho habla el formato chat/completions en todos sus adapters (tool-use,
visión, parseo de usage), por eso se usa el compatible.

Docs: https://docs.x.ai/docs/api-reference
"""

from __future__ import annotations

import time

import httpx

from ..base import Adapter, ErrorPermanente, ErrorTransitorio, FaltaCredencial, Resultado
from ..capacidades import Capability

MODELO_DEFAULT = "grok-4.5"
API_URL = "https://api.x.ai/v1/chat/completions"

# Tarifa oficial por modelo, USD por MILLÓN de tokens (entrada, salida).
# Fuente: https://docs.x.ai/developers/pricing — consultada el 2026-09-28.
# Se busca por prefijo más largo, así «grok-4.20-0309-reasoning» cae en «grok-4.20».
TARIFAS: dict[str, tuple[float, float]] = {
    "grok-4.7": (2.00, 6.00),
    "grok-4.6": (2.00, 6.00),
    "grok-4.5": (2.00, 6.00),
    "grok-4.3": (1.25, 2.50),
    "grok-4.20": (1.25, 2.50),
    "grok-build": (1.00, 2.00),
}
# A partir de este tamaño de prompt xAI cobra TODA la petición al doble.
UMBRAL_CONTEXTO_LARGO = 200_000


def tarifa(modelo: str, prompt_tokens: int = 0) -> tuple[float, float]:
    """USD por TOKEN (entrada, salida) del modelo. Un modelo que no esté en la
    tabla se cobra como el default: mejor una estimación cercana que un cero."""
    m = (modelo or "").lower()
    clave = max((k for k in TARIFAS if m.startswith(k)), key=len, default=MODELO_DEFAULT)
    ent, sal = TARIFAS[clave]
    if prompt_tokens >= UMBRAL_CONTEXTO_LARGO:
        ent, sal = ent * 2, sal * 2
    return ent / 1_000_000, sal / 1_000_000


PRECIO_IN, PRECIO_OUT = tarifa(MODELO_DEFAULT)
MODELOS_CURADOS = ("grok-4.5", "grok-4.7", "grok-4.6", "grok-4.3", "grok-build-0.1")


class GrokAdapter(Adapter):
    nombre = "grok"
    apodo = "Chalán Grok"
    capacidades = frozenset({Capability.TEXTO, Capability.VISION, Capability.FUNCTION_CALLING})
    modelo_default = MODELO_DEFAULT
    modelos_curados = MODELOS_CURADOS

    def __init__(self, modelo: str = MODELO_DEFAULT, timeout: float = 30.0):
        self.modelo = modelo
        self.timeout = timeout

    def _llave(self) -> str:
        from ajustes.models.credencial import Credencial
        llave = Credencial.obtener("chalan_grok_api_key")
        if not llave:
            raise FaltaCredencial("chalan_grok_api_key no configurada en Los Ajustes")
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
            raise ErrorTransitorio(f"grok: red/timeout — {exc}") from exc
        latencia = int((time.monotonic() - t0) * 1000)

        if resp.status_code in (401, 403):
            raise ErrorPermanente(f"grok: auth {resp.status_code}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErrorTransitorio(f"grok: {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ErrorPermanente(f"grok: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        choices = data.get("choices") or []
        texto = (choices[0].get("message", {}).get("content") if choices else "") or ""
        usage = data.get("usage") or {}
        pt = int(usage.get("prompt_tokens") or 0)
        ct = int(usage.get("completion_tokens") or 0)
        precio_in, precio_out = tarifa(data.get("model") or self.modelo, pt)
        costo = pt * precio_in + ct * precio_out
        return Resultado(
            texto=texto, provider=self.nombre, modelo=data.get("model") or self.modelo,
            prompt_tokens=pt, completion_tokens=ct, costo_usd=round(costo, 6),
            latencia_ms=latencia,
        )

    def _invocar_chat(self, mensajes, *, max_tokens, temperatura, herramientas=None,
                      imagenes=None) -> Resultado:
        from ..herramientas_formato import herramientas_openai, mensajes_openai, parsear_openai
        llave = self._llave()
        body = {
            "model": self.modelo,
            "max_tokens": max_tokens,
            "temperature": temperatura,
            "messages": mensajes_openai(mensajes),
        }
        if herramientas:
            body["tools"] = herramientas_openai(herramientas)
        t0 = time.monotonic()
        try:
            resp = httpx.post(
                API_URL,
                headers={"Authorization": f"Bearer {llave}", "content-type": "application/json"},
                json=body,
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ErrorTransitorio(f"grok: red/timeout — {exc}") from exc
        latencia = int((time.monotonic() - t0) * 1000)

        if resp.status_code in (401, 403):
            raise ErrorPermanente(f"grok: auth {resp.status_code}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErrorTransitorio(f"grok: {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ErrorPermanente(f"grok: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        pt = int((data.get("usage") or {}).get("prompt_tokens") or 0)
        precio_in, precio_out = tarifa(data.get("model") or self.modelo, pt)
        return parsear_openai(
            data, provider=self.nombre, modelo=self.modelo, latencia_ms=latencia,
            precio_in=precio_in, precio_out=precio_out,
        )

    def listar_modelos(self) -> list[str]:
        try:
            llave = self._llave()
        except Exception:
            return list(MODELOS_CURADOS)
        try:
            resp = httpx.get(
                "https://api.x.ai/v1/models",
                headers={"Authorization": f"Bearer {llave}"},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return list(MODELOS_CURADOS)
            ids = [m.get("id") for m in (resp.json().get("data") or []) if m.get("id")]
            return ids or list(MODELOS_CURADOS)
        except Exception:
            return list(MODELOS_CURADOS)

    def consultar_saldo(self) -> dict:
        """xAI no expone un endpoint público de saldo. Reportamos
        `soportado=False`; la UI muestra el uso (llamadas/tokens/costo) que ya
        viene de `AnalistaLog` y un link a la consola de xAI."""
        return {"soportado": False, "disponible": None, "moneda": "USD",
                "etiqueta": "Ver en consola",
                "fuente_url": "https://console.x.ai/",
                "mensaje": "xAI no expone saldo por API; revisa el uso (llamadas, tokens y costo) o la consola."}
