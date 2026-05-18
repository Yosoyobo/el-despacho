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
    """Interfaz común. Cada provider implementa `nombre`, `apodo`,
    `capacidades` y `_invocar`.

    v2 (pre-S2b.1): cada Chalán declara `apodo` (UI) y `capacidades`
    (set de Capability). El Reemplazo salta Chalanes que no soportan la
    capability requerida.
    """

    nombre: str = ""
    apodo: str = ""
    capacidades: frozenset = frozenset()

    @abstractmethod
    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float) -> Resultado: ...

    def analizar(self, prompt: str, *, max_tokens: int = 400, temperatura: float = 0.4) -> Resultado:
        return self._invocar(prompt, max_tokens=max_tokens, temperatura=temperatura)

    def esta_configurado(self) -> bool:
        """Default: intenta cargar la llave; subclases sin `_llave` retornan False."""
        llave_fn = getattr(self, "_llave", None)
        if llave_fn is None:
            return False
        try:
            llave_fn()
            return True
        except Exception:
            return False


# Alias semántico para el código nuevo de v2.
AdapterChalan = Adapter
