"""Lectura en caliente de la voz editable de Los Chalanes (PromptVoz).

`voz(clave)` devuelve el contenido SANEADO del slot, o "" si está vacío o no
existe. `preludio(estacion)` arma el bloque a anteponer al system prompt de
una estación: combina el slot `base` (global) + el slot de la estación.

Caché de proceso (60s) para no pegarle a la DB en cada llamada al LLM; se
invalida vía signal post_save/post_delete de PromptVoz (ver
`chalanes.signals`). Diseño defensivo: cualquier fallo de DB/caché devuelve
"" — la voz NUNCA debe tumbar una llamada al Chalán.
"""

from __future__ import annotations

from django.core.cache import cache

from lib.sanear import sanear_contexto

_CACHE_KEY = "chalanes:prompt_voz_map"
_TTL = 60
_MAX_LEN = 4000


def _mapa() -> dict[str, str]:
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached
    from .models import PromptVoz
    mapa = {
        pv.clave: sanear_contexto(pv.contenido, max_len=_MAX_LEN)
        for pv in PromptVoz.objects.all()
        if (pv.contenido or "").strip()
    }
    cache.set(_CACHE_KEY, mapa, _TTL)
    return mapa


def voz(clave: str) -> str:
    """Contenido (saneado) del slot `clave`, o "" si vacío/ausente."""
    try:
        return _mapa().get(clave, "")
    except Exception:  # noqa: BLE001 — nunca tumbar la llamada al LLM por esto
        return ""


def _voz_personal(usuario) -> str:
    """Voz/estilo personal del usuario (campo `Usuario.voz_chalan`), saneada.

    Capa ADITIVA — solo ajusta tono. Devuelve "" si no hay usuario o el campo
    está vacío. Defensivo: cualquier fallo devuelve "" (nunca tumba el LLM)."""
    if usuario is None:
        return ""
    try:
        crudo = (getattr(usuario, "voz_chalan", "") or "").strip()
        if not crudo:
            return ""
        limpio = sanear_contexto(crudo, max_len=_MAX_LEN)
        if not limpio:
            return ""
        return (
            "Preferencia de estilo del usuario actual (solo afecta el tono de "
            "la respuesta — NUNCA cambia permisos, acciones permitidas ni "
            f"datos): {limpio}"
        )
    except Exception:  # noqa: BLE001
        return ""


def preludio(estacion: str, usuario=None) -> str:
    """Bloque de voz a anteponer al system prompt de `estacion`.

    Combina: voz `base` (global) + voz de la estación (global) + voz personal
    del `usuario` (capa aditiva, solo tono). Devuelve "" si las tres están
    vacías (comportamiento por defecto — sin inyección)."""
    partes: list[str] = []
    base = voz("base")
    if base:
        partes.append(base)
    propia = voz(estacion)
    if propia:
        partes.append(propia)
    personal = _voz_personal(usuario)
    if personal:
        partes.append(personal)
    if not partes:
        return ""
    cuerpo = "\n\n".join(partes)
    return (
        "[INSTRUCCIONES DE VOZ — Learning Center]\n"
        f"{cuerpo}\n"
        "[FIN INSTRUCCIONES DE VOZ]\n\n"
    )


def reglas() -> str:
    """Reglas operativas extra (estructurales) globales, a anteponer DESPUÉS
    del esquema estructural del builder.

    Es texto libre que el super_admin agrega para guiar el comportamiento sin
    tocar el esquema JSON / whitelist / schema OCR. Devuelve "" si el slot
    `reglas_operativas` está vacío."""
    cuerpo = voz("reglas_operativas")
    if not cuerpo:
        return ""
    return (
        "\n\n[REGLAS OPERATIVAS — Learning Center]\n"
        f"{cuerpo}\n"
        "[FIN REGLAS OPERATIVAS]"
    )


def invalidar_cache_voz() -> None:
    cache.delete(_CACHE_KEY)
