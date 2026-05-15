"""Tipos comunes para Los Analistas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Resultado:
    """Respuesta normalizada de un adapter. `texto` es la salida principal;
    el resto sirve para Los Analistas Log y para reportes de costo."""

    texto: str
    provider: str
    modelo: str
    prompt_tokens: int
    completion_tokens: int
    costo_usd: float
    latencia_ms: int


class ErrorTransitorio(Exception):
    """Error que justifica intentar el siguiente adapter en la cadena
    (red caída, rate-limit, 5xx)."""


class ErrorPermanente(Exception):
    """Error que NO debe disparar fallback (prompt inválido, auth incorrecta,
    contenido bloqueado por política). La cadena se detiene y propaga."""


class FaltaCredencial(ErrorTransitorio):
    """El adapter no tiene su llave configurada — no consume retry-budget."""


class Adapter(ABC):
    """Interfaz común. Cada provider implementa `nombre` y `_invocar`."""

    nombre: str = ""

    @abstractmethod
    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float) -> Resultado: ...

    def analizar(self, prompt: str, *, max_tokens: int = 400, temperatura: float = 0.4) -> Resultado:
        return self._invocar(prompt, max_tokens=max_tokens, temperatura=temperatura)
