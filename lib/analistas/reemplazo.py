"""El Reemplazo — cadena de fallback entre adapters.

`analizar()` itera la cadena de la estación: el primer adapter intenta;
si falla con ErrorTransitorio o FaltaCredencial, intenta el siguiente; si
falla con ErrorPermanente, propaga sin intentar más. Cada intento se loguea
en `ajustes_analistas_log`.
"""

from __future__ import annotations

from .base import ErrorPermanente, ErrorTransitorio, Resultado
from .log import hash_prompt, registrar_intento
from .registry import cadena_de


class TodosLosAnalistasFallaron(Exception):
    def __init__(self, intentos: list[tuple[str, str]]):
        self.intentos = intentos
        msg = "; ".join(f"{p}: {err}" for p, err in intentos)
        super().__init__(f"Cadena agotada — {msg}")


def analizar(
    estacion: str,
    prompt: str,
    *,
    max_tokens: int = 400,
    temperatura: float = 0.4,
    actor_id: int | None = None,
) -> Resultado:
    cadena = cadena_de(estacion)
    if not cadena:
        raise RuntimeError(f"No hay adapters configurados para estación '{estacion}'")
    ph = hash_prompt(prompt)
    intentos_fallidos: list[tuple[str, str]] = []
    for adapter in cadena:
        try:
            res = adapter.analizar(prompt, max_tokens=max_tokens, temperatura=temperatura)
        except ErrorPermanente as exc:
            registrar_intento(
                estacion=estacion, prompt_hash=ph, provider=adapter.nombre,
                modelo=getattr(adapter, "modelo", ""), exito=False,
                mensaje_error=str(exc), actor_id=actor_id,
            )
            raise
        except ErrorTransitorio as exc:
            registrar_intento(
                estacion=estacion, prompt_hash=ph, provider=adapter.nombre,
                modelo=getattr(adapter, "modelo", ""), exito=False,
                mensaje_error=str(exc), actor_id=actor_id,
            )
            intentos_fallidos.append((adapter.nombre, str(exc)))
            continue
        registrar_intento(
            estacion=estacion, prompt_hash=ph, provider=res.provider, modelo=res.modelo,
            exito=True, resultado=res, actor_id=actor_id,
        )
        return res
    raise TodosLosAnalistasFallaron(intentos_fallidos)
