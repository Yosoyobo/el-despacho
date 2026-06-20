"""Registry de adapters + lookup de cadena DB-aware (Chalanes v2).

`cadena_de(estacion, usuario_id=None)` consulta:
  1. `ChalanAsignado(usuario, estacion)` → override personal, si existe.
  2. `CuadroChalanes(estacion)` → preferencia del equipo.
  3. Hardcoded ['anthropic', 'openai'] → fallback de emergencia (DB vacía).

Luego agrega los demás Chalanes de la `CadenaFallback` activa, en orden de
prioridad ASC, omitiendo duplicados.
"""

from __future__ import annotations

from .adapters import (
    AnthropicAdapter,
    DeepseekAdapter,
    GeminiAdapter,
    MimoAdapter,
    OllamaAdapter,
    OpenAIAdapter,
)
from .base import Adapter

# Map nombre → factory. Los 5 Chalanes cloud están activos a partir de
# S-Demo-Pre-Showcase (2026-05-24). 'ollama' es el Chalán Llama (Test): servidor
# local/self-hosted (Tailscale), no entra solo al fallback global.
_FACTORIES: dict[str, type[Adapter]] = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
    "deepseek": DeepseekAdapter,
    "mimo": MimoAdapter,
    "gemini": GeminiAdapter,
    "ollama": OllamaAdapter,
}

# Fallback de seguridad si las tablas chalanes_* no existen aún.
CADENA_DEFAULT = ("anthropic", "openai")


def adapter_de(nombre: str, modelo: str | None = None) -> Adapter | None:
    factory = _FACTORIES.get(nombre)
    if factory is None:
        return None
    if modelo:
        return factory(modelo=modelo)
    return factory()


def apodo(nombre: str) -> str:
    """Para mostrar en UI: 'anthropic' → 'Chalán Claudio'."""
    factory = _FACTORIES.get(nombre)
    if factory is None:
        return nombre
    return getattr(factory, "apodo", nombre) or nombre


def modelo_default_de(nombre: str) -> str:
    """Modelo predeterminado de un proveedor (espejo de su MODELO_DEFAULT)."""
    factory = _FACTORIES.get(nombre)
    if factory is None:
        return ""
    return getattr(factory, "modelo_default", "") or ""


def modelos_por_proveedor(forzar: bool = False) -> dict[str, list[str]]:
    """Mapa {proveedor: [modelos disponibles]} para poblar el dropdown del Cuadro.

    Consulta cada adapter (que pega a la API del proveedor con las credenciales
    actuales) y cachea ~1h en el cache de Django. `forzar=True` ignora el cache.
    Best-effort: un proveedor sin llave o con la API caída cae a su lista curada.
    """
    try:
        from django.core.cache import cache
    except Exception:
        cache = None
    out: dict[str, list[str]] = {}
    for nombre, factory in _FACTORIES.items():
        clave = f"chalan_modelos_{nombre}"
        modelos = None if forzar else (cache.get(clave) if cache else None)
        if modelos is None:
            try:
                modelos = factory().listar_modelos()
            except Exception:
                modelos = []
            if cache:
                cache.set(clave, modelos, 3600)
        out[nombre] = modelos
    return out


def modelo_valido(proveedor: str, modelo: str) -> str:
    """Normaliza el modelo para un proveedor.

    Si el modelo no está entre los disponibles del proveedor (cross-wiring),
    devuelve el MODELO_DEFAULT del proveedor. Si no se pudo listar (API caída),
    respeta lo que venga. Vacío → default.
    """
    if proveedor not in _FACTORIES:
        return modelo
    if not modelo:
        return modelo_default_de(proveedor)
    disponibles = modelos_por_proveedor().get(proveedor) or []
    if disponibles and modelo not in disponibles:
        return modelo_default_de(proveedor) or modelo
    return modelo


def _resolver_primario(estacion: str, usuario_id: int | None) -> tuple[str, str | None] | None:
    try:
        from chalanes.models import ChalanAsignado, CuadroChalanes
    except Exception:
        return None
    if usuario_id is not None:
        try:
            asignado = ChalanAsignado.objects.filter(usuario_id=usuario_id, estacion=estacion).first()
        except Exception:
            asignado = None
        if asignado:
            return (asignado.proveedor, asignado.modelo or None)
    try:
        cuadro = CuadroChalanes.objects.filter(estacion=estacion).first()
    except Exception:
        cuadro = None
    if cuadro:
        return (cuadro.proveedor, cuadro.modelo)
    return None


def _orden_fallback() -> list[str]:
    try:
        from chalanes.models import CadenaFallback
        return list(
            CadenaFallback.objects.filter(activo=True).order_by("prioridad").values_list("proveedor", flat=True)
        )
    except Exception:
        return list(CADENA_DEFAULT)


def cadena_de(estacion: str, usuario_id: int | None = None) -> list[Adapter]:
    """Devuelve la lista ordenada de adapters a intentar."""
    nombres: list[str] = []

    primario = _resolver_primario(estacion, usuario_id)
    if primario is not None:
        nombres.append(primario[0])

    for n in _orden_fallback():
        if n not in nombres:
            nombres.append(n)

    if not nombres:
        nombres = list(CADENA_DEFAULT)

    cadena: list[Adapter] = []
    for n in nombres:
        if n not in _FACTORIES:
            continue
        modelo = primario[1] if (primario and primario[0] == n) else None
        adapter = adapter_de(n, modelo=modelo)
        if adapter:
            cadena.append(adapter)
    return cadena
