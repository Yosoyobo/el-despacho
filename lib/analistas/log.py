"""Logueo de cada intento de Los Analistas a `ajustes_analistas_log`.

Se registra el HASH del prompt (sha256), nunca el prompt en claro. Esto
balancea: La Sala de Juntas tiene métricas de uso/costo/error pero no
expone contenido del cliente al admin.
"""

from __future__ import annotations

import hashlib

from .base import Resultado


def hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def registrar_intento(
    *,
    estacion: str,
    prompt_hash: str,
    provider: str,
    modelo: str,
    exito: bool,
    resultado: Resultado | None = None,
    mensaje_error: str = "",
    actor_id: int | None = None,
) -> None:
    """Persiste el intento. Import perezoso de Django para no acoplar el módulo
    a apps cargadas (tests sin Django pueden mockear)."""
    try:
        from ajustes.models.analistas_log import AnalistaLog
    except ImportError:
        return  # Django/app no cargada (uso aislado de la lib).

    fields = {
        "estacion": estacion,
        "prompt_hash": prompt_hash,
        "provider": provider,
        "modelo": modelo,
        "exito": exito,
        "mensaje_error": (mensaje_error or "")[:1000],
        "actor_id": actor_id,
    }
    if resultado is not None:
        fields.update(
            prompt_tokens=resultado.prompt_tokens,
            completion_tokens=resultado.completion_tokens,
            costo_usd_estimado=resultado.costo_usd,
            latencia_ms=resultado.latencia_ms,
        )
    AnalistaLog.objects.create(**fields)
