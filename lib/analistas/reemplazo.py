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
        # Un Chalán sin credencial se SALTA en silencio (también el primario):
        # no se intenta ni se loguea en rojo. Así, quitar la llave de un
        # proveedor lo retira del relevo de inmediato sin ensuciar la auditoría.
        # Si NINGUNO tiene llave, la cadena se agota → TodosFallaron (error claro).
        if not adapter.esta_configurado():
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


def _texto_para_hash(mensajes: list[dict]) -> str:
    """Hash de la conversación = último turno de usuario (suficiente para
    agrupar el log; no necesitamos el prompt completo)."""
    for m in reversed(mensajes):
        if m.get("rol") == "user" and m.get("texto"):
            return m["texto"]
    return "(chat)"


def _tiene_imagenes(mensajes: list[dict]) -> bool:
    return any(m.get("imagenes") for m in mensajes)


def chatear(
    estacion: str,
    mensajes: list[dict],
    *,
    herramientas: list | None = None,
    max_tokens: int = 700,
    temperatura: float = 0.3,
    actor_id: int | None = None,
    requiere: set | None = None,
    excluir: set[str] | None = None,
) -> Resultado:
    """Modo conversación con tool-use NATIVO (S-Chalan-Agente Fase 1).

    Paralelo a `analizar()` pero recibe una conversación canónica + specs de
    herramientas. Reusa la misma cadena DB-aware, el gate de presupuesto y el
    log. Cuando se pasan `herramientas`, EXIGE adapters con FUNCTION_CALLING; si
    la conversación trae imágenes, EXIGE VISION (igual que `analizar`).

    Devuelve el `Resultado` del primer adapter que respondió — con `tool_calls`
    lleno si el modelo pidió herramientas. El orquestador las ejecuta y vuelve
    a llamar con los `tool_result` agregados a `mensajes`."""
    from .capacidades import Capability

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

    requiere = set(requiere or set())
    if herramientas:
        requiere |= {Capability.FUNCTION_CALLING}
    if _tiene_imagenes(mensajes):
        requiere |= {Capability.VISION}

    if excluir:
        cadena = [a for a in cadena if a.nombre not in excluir]
    if requiere:
        cadena = [a for a in cadena if set(requiere).issubset(set(a.capacidades or ()))]
    if not cadena:
        raise TodosFallaron([("(filtro_capacidad)", f"ninguno soporta {requiere}")])

    ph = hash_prompt(_texto_para_hash(mensajes))
    intentos_fallidos: list[tuple[str, str]] = []
    primario = cadena[0].nombre

    for i, adapter in enumerate(cadena):
        es_fallback = i > 0
        # Igual que `analizar`: salta en silencio a quien no tenga llave (incl.
        # el primario) para no intentar/loguear un Chalán sin credencial.
        if not adapter.esta_configurado():
            intentos_fallidos.append((adapter.nombre, "sin credencial — saltado"))
            continue
        try:
            res = adapter.chatear(
                mensajes, herramientas=herramientas,
                max_tokens=max_tokens, temperatura=temperatura,
            )
        except (ErrorPermanente, ErrorTransitorio) as exc:
            registrar_intento(
                estacion=estacion, prompt_hash=ph, provider=adapter.nombre,
                modelo=getattr(adapter, "modelo", ""), exito=False,
                mensaje_error=str(exc), actor_id=actor_id,
                es_fallback=es_fallback, proveedor_original=primario if es_fallback else None,
            )
            intentos_fallidos.append((adapter.nombre, str(exc)))
            continue
        registrar_intento(
            estacion=estacion, prompt_hash=ph, provider=res.provider, modelo=res.modelo,
            exito=True, resultado=res, actor_id=actor_id,
            es_fallback=es_fallback, proveedor_original=primario if es_fallback else None,
        )
        return res
    raise TodosFallaron(intentos_fallidos)


__all__ = ["analizar", "chatear", "TodosLosAnalistasFallaron", "TodosFallaron"]
