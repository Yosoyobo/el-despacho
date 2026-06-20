"""Chalán Llama (Test) — adapter Ollama (servidor local, API compatible OpenAI).

Ollama es un servidor de modelos local/self-hosted. En El Despacho se usa como
**Chalán de pruebas**: corre en otro nodo de la red Tailscale (ej. la NUC en
`http://100.120.28.93:11434`) y sirve modelos abiertos (llama, qwen, mistral…).

Diferencias clave vs los demás Chalanes:
  - **No usa API key.** El "secreto" configurable es el **base URL** del
    servidor, que vive en el slot `chalan_ollama_base_url` de Los Ajustes.
    Sin ese slot el adapter lanza `FaltaCredencial` y El Reemplazo lo salta.
  - **Costo $0** — es local. El conteo de tokens (AnalistaLog) sigue siendo
    exacto; el costo estimado queda en 0.
  - Endpoint compatible con OpenAI en `{base}/v1/chat/completions`; el listado
    de modelos usa el endpoint nativo `{base}/api/tags`.
  - NO se auto-agrega a la cadena de fallback global (el slot no es
    `chalan_<prov>_api_key`, así que el signal de auto-fallback no lo engancha).
    El super_admin lo asigna a una estación a mano desde `/chalanes/`. Es a
    propósito: un servidor local de pruebas que puede estar apagado no debe
    inyectarse solo en el relevo de producción.

Docs Ollama: https://github.com/ollama/ollama/blob/main/docs/openai.md
"""

from __future__ import annotations

import time

import httpx

from ..base import Adapter, ErrorPermanente, ErrorTransitorio, FaltaCredencial, Resultado
from ..capacidades import Capability

MODELO_DEFAULT = "llama3.2"
SLOT_BASE_URL = "chalan_ollama_base_url"
# Local / self-hosted → sin costo. El token-count sigue siendo exacto.
PRECIO_IN = 0.0
PRECIO_OUT = 0.0
MODELOS_CURADOS = ("llama3.2", "llama3.1", "qwen2.5", "mistral", "gemma2")


class OllamaAdapter(Adapter):
    nombre = "ollama"
    apodo = "Chalán Llama"
    capacidades = frozenset({Capability.TEXTO, Capability.FUNCTION_CALLING})
    modelo_default = MODELO_DEFAULT
    modelos_curados = MODELOS_CURADOS
    # El "credencial" de Ollama es el base URL, no una API key. El panel de
    # Chalanes (stats.tarjetas_chalanes) lee este slot en vez de
    # `chalan_<nombre>_api_key`.
    slot_credencial = SLOT_BASE_URL

    def __init__(self, modelo: str = MODELO_DEFAULT, timeout: float = 60.0):
        # Ollama local puede tardar más en cargar el modelo en frío → timeout
        # más holgado que los proveedores cloud.
        self.modelo = modelo
        self.timeout = timeout

    def _base_url(self) -> str:
        """Devuelve el base URL del servidor Ollama (sin slash final), o lanza
        FaltaCredencial si el slot no está configurado en Los Ajustes."""
        from ajustes.models.credencial import Credencial
        url = Credencial.obtener(SLOT_BASE_URL)
        if not url:
            raise FaltaCredencial(
                f"{SLOT_BASE_URL} no configurado en Los Ajustes "
                "(ej. http://100.120.28.93:11434)"
            )
        return url.strip().rstrip("/")

    def esta_configurado(self) -> bool:
        try:
            self._base_url()
            return True
        except Exception:
            return False

    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float,
                 imagenes: list | None = None) -> Resultado:
        # Ollama no declara VISION aquí (depende del modelo cargado); el
        # Reemplazo lo salta si se piden imágenes. `imagenes` se ignora.
        base = self._base_url()
        t0 = time.monotonic()
        try:
            resp = httpx.post(
                f"{base}/v1/chat/completions",
                headers={"content-type": "application/json"},
                json={
                    "model": self.modelo,
                    "max_tokens": max_tokens,
                    "temperature": temperatura,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ErrorTransitorio(f"ollama: red/timeout — {exc}") from exc
        latencia = int((time.monotonic() - t0) * 1000)

        if resp.status_code in (401, 403):
            raise ErrorPermanente(f"ollama: auth {resp.status_code}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErrorTransitorio(f"ollama: {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ErrorPermanente(f"ollama: {resp.status_code} {resp.text[:200]}")

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

    def _invocar_chat(self, mensajes, *, max_tokens, temperatura, herramientas=None,
                      imagenes=None) -> Resultado:
        from ..herramientas_formato import herramientas_openai, mensajes_openai, parsear_openai
        base = self._base_url()
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
                f"{base}/v1/chat/completions",
                headers={"content-type": "application/json"},
                json=body,
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ErrorTransitorio(f"ollama: red/timeout — {exc}") from exc
        latencia = int((time.monotonic() - t0) * 1000)

        if resp.status_code in (401, 403):
            raise ErrorPermanente(f"ollama: auth {resp.status_code}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErrorTransitorio(f"ollama: {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ErrorPermanente(f"ollama: {resp.status_code} {resp.text[:200]}")

        return parsear_openai(
            resp.json(), provider=self.nombre, modelo=self.modelo, latencia_ms=latencia,
            precio_in=PRECIO_IN, precio_out=PRECIO_OUT,
        )

    def listar_modelos(self) -> list[str]:
        """Lista los modelos realmente descargados en el servidor Ollama vía el
        endpoint nativo `GET {base}/api/tags`. Cae a los curados si no hay base
        URL configurado o el servidor no responde."""
        try:
            base = self._base_url()
        except Exception:
            return list(MODELOS_CURADOS)
        try:
            resp = httpx.get(f"{base}/api/tags", timeout=self.timeout)
            if resp.status_code != 200:
                return list(MODELOS_CURADOS)
            modelos = [m.get("name") for m in (resp.json().get("models") or []) if m.get("name")]
            return modelos or list(MODELOS_CURADOS)
        except Exception:
            return list(MODELOS_CURADOS)

    def consultar_saldo(self) -> dict:
        """Ollama es local — no hay saldo que consultar."""
        return {"soportado": False, "disponible": None, "moneda": "USD",
                "etiqueta": "Local (sin costo)",
                "fuente_url": "",
                "mensaje": "Ollama corre local/self-hosted; no consume saldo."}
