"""Registry de adapters + lookup de cadena DB-aware (Chalanes v2).

`cadena_de(estacion, usuario_id=None)` consulta:
  1. `ChalanAsignado(usuario, estacion)` → override personal, si existe.
  2. `CuadroChalanes(estacion)` → preferencia del equipo.
  3. Hardcoded ['anthropic', 'openai'] → fallback de emergencia (DB vacía).

Luego agrega los demás Chalanes de la `CadenaFallback` activa, en orden de
prioridad ASC, omitiendo duplicados.
"""

from __future__ import annotations

from .adapters import AnthropicAdapter, DeepseekAdapter, OpenAIAdapter
from .base import Adapter

# Map nombre → factory. Gemini no se registra aún (skeleton).
_FACTORIES: dict[str, type[Adapter]] = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
    "deepseek": DeepseekAdapter,
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
