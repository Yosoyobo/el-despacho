"""Servicios de El Dictado — interpretación + aplicación.

`interpretar(texto, usuario)`:
- Crea `Dictado(estado='interpretando')`
- Construye prompt con aprendizajes activos + contexto
- Llama `lib.analistas.analizar(estacion='dictado', ...)`
- Parsea JSON de respuesta
- Persiste `DictadoAccion`s o `pregunta_clarificacion`
- Setea estado final: `esperando_confirmacion` | `preguntando` | `fallo_ia`

`aplicar(dictado, usuario)`:
- Itera `acciones.filter(confirmada=True).order_by('orden')`
- Llama ejecutor[tipo] — captura excepciones por acción (no aborta resto)
- Persiste estado final: `aplicado` | `aplicado_con_errores`
- Emite eventos del Portavoz

Acciones globalmente prohibidas (DOC_04 §5.3) se filtran ANTES del save.
"""

from __future__ import annotations

import json
import logging
import time

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# Tipos que NUNCA se ejecutan (filtrados antes de persistir acciones).
TIPOS_PROHIBIDOS = {
    "modificar_ajustes", "modificar_catalogo", "modificar_tasas",
    "modificar_centro_costo", "modificar_permisos", "eliminar_entidad",
}


def interpretar(
    *,
    texto: str | None = None,
    usuario,
    origen: str = "sala_juntas",
    aclaracion: str | None = None,
    dictado=None,
):
    """Interpreta un dictado (nuevo o re-iteración tras clarificación).

    Si `dictado=None`, crea uno nuevo con `texto_crudo=texto`.
    Si `dictado` se pasa (caso S2b.2.1 — el usuario respondió la pregunta
    del Chalán), reusa el registro, limpia acciones previas y vuelve a
    interpretar con el historial de clarificaciones acumulado en el
    prompt. La respuesta del usuario debe haberse agregado al
    `historial_clarificaciones` por el caller ANTES de invocar.

    Retorna el `Dictado` con estado final. Nunca lanza — los errores LLM
    quedan capturados en `estado='fallo_ia'`.
    """
    from .models import Dictado, DictadoAccion
    from .prompt import SYSTEM_PROMPT, aprendizajes_activos, construir_user_prompt

    if dictado is None:
        texto = (texto or "").strip()
        if not texto:
            raise ValueError("Texto del dictado vacío.")
        dictado = Dictado.objects.create(
            autor=usuario, texto_crudo=texto, estado="interpretando", origen=origen,
        )
    else:
        # Re-iteración: limpiamos acciones previas y reseteamos estado.
        dictado.acciones.all().delete()
        dictado.estado = "interpretando"
        dictado.pregunta_clarificacion = ""
        dictado.save(update_fields=["estado", "pregunta_clarificacion"])
        texto = dictado.texto_crudo

    aprendizajes = aprendizajes_activos()
    user_prompt = construir_user_prompt(
        usuario=usuario, texto_crudo=texto,
        aprendizajes=aprendizajes, aclaracion=aclaracion,
        historial=list(dictado.historial_clarificaciones or []),
    )
    from chalanes.voz import preludio, reglas
    prompt_completo = preludio("dictado", usuario) + SYSTEM_PROMPT + reglas() + "\n\n" + user_prompt

    # Resuelve los `@usuario/#proyecto/$cliente` del dictado + clarificaciones a
    # entidades reales para que el LLM sepa el código/nombre exactos (mismo
    # tratamiento que el chat de El Chalán). Reusa la fuente única compartida.
    from referencias.bloque import bloque_prompt
    texto_referencias = " ".join(
        [texto or ""]
        + [str(t.get("respuesta", "")) for t in (dictado.historial_clarificaciones or [])]
        + ([aclaracion] if aclaracion else []),
    )
    prompt_completo += bloque_prompt(texto_referencias)

    t0 = time.monotonic()
    try:
        from lib.analistas import analizar
        resultado = analizar(
            estacion="dictado", prompt=prompt_completo,
            max_tokens=2000, temperatura=0.2, actor_id=getattr(usuario, "pk", None),
        )
    except Exception as exc:  # noqa: BLE001 — fallo total (incluye TodosFallaron)
        logger.warning("dictado=%s LLM falló: %s", dictado.pk, exc)
        dictado.estado = "fallo_ia"
        dictado.interpretacion_raw = {"error": str(exc)}
        dictado.save(update_fields=["estado", "interpretacion_raw"])
        return dictado

    latencia_ms = int((time.monotonic() - t0) * 1000)
    dictado.latencia_interpretacion_ms = latencia_ms
    dictado.chalan = resultado.provider
    dictado.chalan_apodo = _apodo_de(resultado.provider)
    dictado.modelo = resultado.modelo

    parsed = _parsear_json(resultado.texto)
    if parsed is None:
        dictado.estado = "fallo_ia"
        dictado.interpretacion_raw = {"raw": resultado.texto[:2000]}
        dictado.save(update_fields=["estado", "interpretacion_raw", "chalan", "chalan_apodo", "modelo", "latencia_interpretacion_ms"])
        return dictado

    dictado.interpretacion_raw = parsed
    pregunta = (parsed.get("pregunta_clarificacion") or "").strip() if isinstance(parsed, dict) else ""
    if pregunta:
        dictado.estado = "preguntando"
        dictado.pregunta_clarificacion = pregunta
        dictado.save(update_fields=[
            "estado", "pregunta_clarificacion", "interpretacion_raw",
            "chalan", "chalan_apodo", "modelo", "latencia_interpretacion_ms",
        ])
        return dictado

    acciones_raw = (parsed.get("acciones") or []) if isinstance(parsed, dict) else []
    # Filtra prohibidas + persiste el resto.
    with transaction.atomic():
        orden = 0
        for raw in acciones_raw:
            if not isinstance(raw, dict):
                continue
            tipo = (raw.get("tipo") or "").strip()
            if not tipo or tipo in TIPOS_PROHIBIDOS:
                continue
            DictadoAccion.objects.create(
                dictado=dictado, orden=orden,
                tipo=tipo,
                descripcion=(raw.get("descripcion") or "")[:300],
                payload=raw.get("payload") or {},
                confianza=float(raw.get("confianza") or 1.0),
            )
            orden += 1
        dictado.estado = "esperando_confirmacion"
        dictado.save(update_fields=[
            "estado", "interpretacion_raw",
            "chalan", "chalan_apodo", "modelo", "latencia_interpretacion_ms",
        ])

    _emitir_evento("dictado.interpretado", usuario, {
        "dictado_id": dictado.pk,
        "num_acciones": dictado.acciones.count(),
        "latencia_ms": latencia_ms,
        "chalan": dictado.chalan,
    })
    return dictado


MAX_REINTENTOS_CHALAN = 2  # 1 primario + 2 fallbacks = 3 Chalanes máximo.


def aplicar(*, dictado, usuario, _reintentos: int = 0, _proveedores_intentados: set | None = None):
    """Ejecuta las acciones `confirmada=True`. Una falla NO aborta el resto.

    Si **todas** las acciones fallan (aplicadas == 0) y aún quedan Chalanes
    sin probar en la cadena, re-interpreta automáticamente con el siguiente
    proveedor (capa B). Cap: `MAX_REINTENTOS_CHALAN` reintentos.
    """
    from .ejecutores import EJECUTORES

    if dictado.autor_id and dictado.autor_id != usuario.pk:
        raise PermissionError("Solo el autor puede aplicar su propio dictado.")

    proveedores_intentados = _proveedores_intentados or set()
    if dictado.chalan:
        proveedores_intentados.add(dictado.chalan)

    acciones = list(dictado.acciones.filter(confirmada=True).order_by("orden"))
    aplicadas = 0
    fallidas = 0
    # Contexto compartido entre ejecutores del mismo dictado. Permite que una
    # acción referencie la entidad creada por otra acción previa vía
    # `@accion_N` en el slug, o fuzzy-match por nombre. Plan 3 capas 1+2.
    contexto: dict = {"entidades_creadas": {}, "actor": usuario}
    for accion in acciones:
        ejecutor = EJECUTORES.get(accion.tipo)
        if not ejecutor:
            accion.error_al_aplicar = f"Sin ejecutor para tipo `{accion.tipo}`."
            accion.save(update_fields=["error_al_aplicar"])
            fallidas += 1
            continue
        try:
            # Retrocompat: ejecutores viejos toman (accion, usuario); los
            # nuevos toman (accion, usuario, contexto). Detectar por arity.
            import inspect
            sig = inspect.signature(ejecutor)
            if len(sig.parameters) >= 3:
                ejecutor(accion, usuario, contexto)
            else:
                ejecutor(accion, usuario)
        except Exception as exc:  # noqa: BLE001
            accion.error_al_aplicar = str(exc)[:1000]
            accion.save(update_fields=["error_al_aplicar"])
            fallidas += 1
            continue
        accion.aplicada = True
        accion.aplicada_en = timezone.now()
        accion.save(update_fields=["aplicada", "aplicada_en", "entidad_tipo", "entidad_id"])
        # Registra la entidad creada para que acciones posteriores la
        # puedan referenciar con `@accion_N`.
        if accion.entidad_tipo and accion.entidad_id:
            contexto["entidades_creadas"][accion.orden] = {
                "tipo": accion.entidad_tipo,
                "id": accion.entidad_id,
            }
        aplicadas += 1

    # Capa B (S-LC-Feedback-V1 hotfix 4): si TODAS las acciones fallaron y aún
    # quedan Chalanes sin probar, re-interpretamos automáticamente con el
    # siguiente proveedor en cadena. Solo aplica al caso "el LLM se equivocó
    # completo" — si al menos una acción cambió DB, NO reintentamos
    # (duplicaría efectos).
    if (
        aplicadas == 0
        and fallidas > 0
        and _reintentos < MAX_REINTENTOS_CHALAN
        and len(acciones) > 0
    ):
        siguiente = _reinterpretar_con_otro_chalan(
            dictado=dictado,
            usuario=usuario,
            excluir=proveedores_intentados,
        )
        if siguiente:
            # Limpia el estado del dictado y aplica las nuevas acciones.
            return aplicar(
                dictado=dictado, usuario=usuario,
                _reintentos=_reintentos + 1,
                _proveedores_intentados=proveedores_intentados,
            )

    dictado.estado = "aplicado" if fallidas == 0 and aplicadas > 0 else (
        "aplicado_con_errores" if aplicadas > 0 else "fallo_ia"
    )
    dictado.aplicado_en = timezone.now()
    dictado.save(update_fields=["estado", "aplicado_en"])

    _emitir_evento(
        "dictado.aplicado_con_errores" if fallidas else "dictado.aplicado",
        usuario,
        {"dictado_id": dictado.pk, "num_aplicadas": aplicadas, "num_fallidas": fallidas},
    )
    return {"aplicadas": aplicadas, "fallidas": fallidas}


def _reinterpretar_con_otro_chalan(*, dictado, usuario, excluir: set):
    """Re-interpreta el dictado con el siguiente Chalán de la cadena.

    Borra las acciones fallidas previas y persiste las nuevas en el mismo
    dictado. Si no hay siguiente Chalán disponible, retorna False y deja
    el dictado como estaba para que `aplicar()` cierre como
    `aplicado_con_errores`/`fallo_ia` normalmente.
    """
    import logging

    from .models import DictadoAccion
    from .prompt import SYSTEM_PROMPT, aprendizajes_activos, construir_user_prompt
    log = logging.getLogger(__name__)

    aprendizajes = aprendizajes_activos()
    user_prompt = construir_user_prompt(
        usuario=usuario, texto_crudo=dictado.texto_crudo,
        aprendizajes=aprendizajes,
        historial=list(dictado.historial_clarificaciones or []),
    )
    from chalanes.voz import preludio, reglas
    prompt_completo = preludio("dictado", usuario) + SYSTEM_PROMPT + reglas() + "\n\n" + user_prompt

    from referencias.bloque import bloque_prompt
    texto_referencias = " ".join(
        [dictado.texto_crudo or ""]
        + [str(t.get("respuesta", "")) for t in (dictado.historial_clarificaciones or [])],
    )
    prompt_completo += bloque_prompt(texto_referencias)

    try:
        from lib.analistas import analizar
        resultado = analizar(
            estacion="dictado", prompt=prompt_completo,
            max_tokens=2000, temperatura=0.2,
            actor_id=getattr(usuario, "pk", None),
            excluir=excluir,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("dictado=%s reinterpretar falló: %s", dictado.pk, exc)
        return False

    parsed = _parsear_json(resultado.texto)
    if not parsed or not isinstance(parsed, dict):
        return False

    # Reemplaza acciones previas con las nuevas. Marcamos las nuevas como
    # confirmada=True automáticamente — el usuario ya confirmó el dictado
    # original; el reintento es transparente.
    dictado.acciones.all().delete()
    acciones_raw = parsed.get("acciones") or []
    orden = 0
    for raw in acciones_raw:
        if not isinstance(raw, dict):
            continue
        tipo = (raw.get("tipo") or "").strip()
        if not tipo or tipo in TIPOS_PROHIBIDOS:
            continue
        DictadoAccion.objects.create(
            dictado=dictado, orden=orden, tipo=tipo,
            descripcion=(raw.get("descripcion") or "")[:300],
            payload=raw.get("payload") or {},
            confianza=float(raw.get("confianza") or 1.0),
            confirmada=True,
        )
        orden += 1
    dictado.chalan = resultado.provider
    dictado.chalan_apodo = _apodo_de(resultado.provider)
    dictado.modelo = resultado.modelo
    dictado.save(update_fields=["chalan", "chalan_apodo", "modelo"])
    _emitir_evento("dictado.reinterpretado", usuario, {
        "dictado_id": dictado.pk,
        "chalan_nuevo": resultado.provider,
        "excluidos": sorted(excluir),
    })
    return True


def _parsear_json(texto: str):
    """Intenta parsear JSON. Si el LLM mete texto antes/después, extrae el {}."""
    if not texto:
        return None
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    # Heurística: buscar primer { y último }
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio < 0 or fin < inicio:
        return None
    try:
        return json.loads(texto[inicio : fin + 1])
    except json.JSONDecodeError:
        return None


def _apodo_de(provider: str) -> str:
    apodos = {
        "anthropic": "Chalán Claudio",
        "openai": "Chalán GPT",
        "deepseek": "Chalán Chino",
        "gemini": "Chalán Gemini",
    }
    return apodos.get(provider, "Chalán")


def _emitir_evento(tipo: str, usuario, payload: dict) -> None:
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo=tipo,  # type: ignore[arg-type]
            actor_id=getattr(usuario, "pk", None),
            actor_email=getattr(usuario, "email", None),
            payload=payload,
        ))
    except Exception:  # noqa: BLE001
        logger.warning("emitir evento %s falló", tipo, exc_info=True)
