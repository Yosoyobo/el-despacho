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
MODELOS_CURADOS = ("deepseek-chat", "deepseek-reasoner")


class DeepseekAdapter(Adapter):
    nombre = "deepseek"
    apodo = "Chalán Chino"
    capacidades = frozenset({Capability.TEXTO, Capability.FUNCTION_CALLING})
    modelo_default = MODELO_DEFAULT
    modelos_curados = MODELOS_CURADOS

    def __init__(self, modelo: str = MODELO_DEFAULT, timeout: float = 30.0):
        self.modelo = modelo
        self.timeout = timeout

    def _llave(self) -> str:
        from ajustes.models.credencial import Credencial
        llave = Credencial.obtener("chalan_deepseek_api_key")
        if not llave:
            raise FaltaCredencial("chalan_deepseek_api_key no configurada en Los Ajustes")
        return llave

    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float,
                 imagenes: list | None = None) -> Resultado:
        # Deepseek no tiene visión (no declara Capability.VISION); el Reemplazo
        # lo salta cuando se piden imágenes. `imagenes` se ignora aquí.
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

    def listar_modelos(self) -> list[str]:
        try:
            llave = self._llave()
        except Exception:
            return list(MODELOS_CURADOS)
        try:
            resp = httpx.get(
                "https://api.deepseek.com/models",
                headers={"Authorization": f"Bearer {llave}", "Accept": "application/json"},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return list(MODELOS_CURADOS)
            ids = [m.get("id") for m in (resp.json().get("data") or []) if m.get("id")]
            return ids or list(MODELOS_CURADOS)
        except Exception:
            return list(MODELOS_CURADOS)

    def consultar_saldo(self) -> dict:
        """Deepseek expone `GET /user/balance` con Bearer.

        Respuesta típica:
        {"is_available": true, "balance_infos": [{"currency": "USD", "total_balance": "5.00", ...}]}
        """
        try:
            llave = self._llave()
        except FaltaCredencial as exc:
            return {"soportado": True, "disponible": None, "moneda": "USD",
                    "etiqueta": "—", "fuente_url": "https://platform.deepseek.com/usage",
                    "mensaje": str(exc)}
        try:
            resp = httpx.get(
                "https://api.deepseek.com/user/balance",
                headers={"Authorization": f"Bearer {llave}", "Accept": "application/json"},
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            return {"soportado": True, "disponible": None, "moneda": "USD",
                    "etiqueta": "—", "fuente_url": "https://platform.deepseek.com/usage",
                    "mensaje": f"red/timeout: {exc}"}
        if resp.status_code != 200:
            return {"soportado": True, "disponible": None, "moneda": "USD",
                    "etiqueta": "—", "fuente_url": "https://platform.deepseek.com/usage",
                    "mensaje": f"HTTP {resp.status_code}"}
        data = resp.json()
        infos = data.get("balance_infos") or []
        if not infos:
            return {"soportado": True, "disponible": 0.0, "moneda": "USD",
                    "etiqueta": "$0.00 USD", "fuente_url": "https://platform.deepseek.com/usage",
                    "mensaje": "Sin saldo activo."}
        # Tomamos USD si existe, si no el primero.
        usd = next((b for b in infos if (b.get("currency") or "").upper() == "USD"), infos[0])
        monto = float(usd.get("total_balance") or 0)
        moneda = (usd.get("currency") or "USD").upper()
        return {"soportado": True, "disponible": monto, "moneda": moneda,
                "etiqueta": f"${monto:,.2f} {moneda}",
                "fuente_url": "https://platform.deepseek.com/usage", "mensaje": "OK"}
