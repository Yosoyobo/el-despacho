"""El Reemplazo — cadena de fallback entre Chalanes (v2).

`analizar()` itera la cadena DB-aware. El primero es el "primario"
(CuadroChalanes/ChalanAsignado). Si falla con ErrorTransitorio,
ErrorPermanente o FaltaCredencial, sigue con el resto de la
CadenaFallback, marcando cada intento posterior con `es_fallback=True`
+ `proveedor_original=<primario>`. Una llave inválida en un proveedor
(p.ej. 401 de Anthropic) no implica nada del resto — cada Chalán tiene
su propia credencial, así que la cadena no debe abortar nunca por un
fallo aislado.

Soporta `requiere` (set de Capability) para saltar Chalanes que no soporten
lo pedido (ej. visión).
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


# Alias semántico v2.
TodosFallaron = TodosLosAnalistasFallaron


def analizar(
    estacion: str,
    prompt: str,
    *,
    max_tokens: int = 400,
    temperatura: float = 0.4,
    actor_id: int | None = None,
    requiere: set | None = None,
    excluir: set[str] | None = None,
    imagenes: list | None = None,
) -> Resultado:
    # Gate de presupuesto IA (S-Directorio-Panel-V1): si el usuario tiene
    # política `topar` y ya rebasó su tope del mes, se rechaza ANTES de llamar
    # a ningún Chalán. La consulta es defensiva (cualquier error → no topa).
    if actor_id:
        debe = False
        try:
            from cuentas.servicios_presupuesto import debe_topar
            debe = debe_topar(actor_id)
        except Exception:
            debe = False
        if debe:
            from .base import PresupuestoIAExcedido
            raise PresupuestoIAExcedido(
                "Alcanzaste tu tope de IA del mes. Pídele al admin que lo amplíe "
                "en El Directorio."
            )

    cadena = cadena_de(estacion, usuario_id=actor_id)
    if not cadena:
        raise RuntimeError(f"No hay adapters configurados para estación '{estacion}'")

    # Si llegan imágenes, solo tienen sentido los Chalanes con visión — los
    # demás producirían basura. Forzamos el filtro de capacidad.
    if imagenes:
        from .capacidades import Capability
        requiere = set(requiere or set()) | {Capability.VISION}

    if excluir:
        cadena = [a for a in cadena if a.nombre not in excluir]
        if not cadena:
            raise TodosFallaron([("(excluidos)", f"todos los proveedores excluidos: {excluir}")])

    if requiere:
        cadena = [a for a in cadena if set(requiere).issubset(set(a.capacidades or ()))]
        if not cadena:
            raise TodosFallaron([("(filtro_capacidad)", f"ninguno soporta {requiere}")])

    ph = hash_prompt(prompt)
    intentos_fallidos: list[tuple[str, str]] = []
    primario = cadena[0].nombre

    for i, adapter in enumerate(cadena):
        es_fallback = i > 0
        if es_fallback and not adapter.esta_configurado():
            intentos_fallidos.append((adapter.nombre, "sin credencial — saltado"))
            continue
        try:
            res = adapter.analizar(prompt, max_tokens=max_tokens, temperatura=temperatura,
                                   imagenes=imagenes)
        except ErrorPermanente as exc:
            registrar_intento(
                estacion=estacion, prompt_hash=ph, provider=adapter.nombre,
                modelo=getattr(adapter, "modelo", ""), exito=False,
                mensaje_error=str(exc), actor_id=actor_id,
                es_fallback=es_fallback,
                proveedor_original=primario if es_fallback else None,
            )
            intentos_fallidos.append((adapter.nombre, str(exc)))
            continue
        except ErrorTransitorio as exc:
            registrar_intento(
                estacion=estacion, prompt_hash=ph, provider=adapter.nombre,
                modelo=getattr(adapter, "modelo", ""), exito=False,
                mensaje_error=str(exc), actor_id=actor_id,
                es_fallback=es_fallback,
                proveedor_original=primario if es_fallback else None,
            )
            intentos_fallidos.append((adapter.nombre, str(exc)))
            continue
        registrar_intento(
            estacion=estacion, prompt_hash=ph, provider=res.provider, modelo=res.modelo,
            exito=True, resultado=res, actor_id=actor_id,
            es_fallback=es_fallback,
            proveedor_original=primario if es_fallback else None,
        )
        return res
    raise TodosFallaron(intentos_fallidos)


__all__ = ["analizar", "TodosLosAnalistasFallaron", "TodosFallaron"]
