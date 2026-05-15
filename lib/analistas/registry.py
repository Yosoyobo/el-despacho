"""Mapeo estación → cadena de adapters.

Estaciones reservadas (las llenará S2b/S4/S5 con casos reales):
- `cotizaciones` — redactar texto de cotización (S2b)
- `gastos` — clasificar gasto (S4)
- `comunicacion` — resumir hilo cliente (S4)
- `precio` — sugerir precio (S4)
- `cliente` — chat con cliente (S5)
- `smoke` — prueba mínima desde Los Ajustes

La cadena DEFAULT es [anthropic → openai]. Cada estación puede sobreescribir
si necesita un orden distinto.
"""

from __future__ import annotations

from .adapters import AnthropicAdapter, OpenAIAdapter
from .base import Adapter

CADENA_DEFAULT = ("anthropic", "openai")

CADENA_POR_ESTACION: dict[str, tuple[str, ...]] = {
    "cotizaciones": CADENA_DEFAULT,
    "gastos": CADENA_DEFAULT,
    "comunicacion": CADENA_DEFAULT,
    "precio": CADENA_DEFAULT,
    "cliente": CADENA_DEFAULT,
    "smoke": CADENA_DEFAULT,
}

_ADAPTERS: dict[str, type[Adapter]] = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
}


def cadena_de(estacion: str) -> list[Adapter]:
    nombres = CADENA_POR_ESTACION.get(estacion, CADENA_DEFAULT)
    return [_ADAPTERS[n]() for n in nombres if n in _ADAPTERS]
