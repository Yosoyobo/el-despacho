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


def interpretar(*, texto: str, usuario, origen: str = "sala_juntas", aclaracion: str | None = None):
    """Crea Dictado + acciones a partir del texto del usuario.

    Retorna el `Dictado` con estado final. Nunca lanza — los errores LLM
    quedan capturados en `estado='fallo_ia'`.
    """
    from .models import Dictado, DictadoAccion
    from .prompt import SYSTEM_PROMPT, aprendizajes_activos, construir_user_prompt

    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Texto del dictado vacío.")

    dictado = Dictado.objects.create(
        autor=usuario, texto_crudo=texto, estado="interpretando", origen=origen,
    )

    aprendizajes = aprendizajes_activos()
    user_prompt = construir_user_prompt(
        usuario=usuario, texto_crudo=texto,
        aprendizajes=aprendizajes, aclaracion=aclaracion,
    )
    prompt_completo = SYSTEM_PROMPT + "\n\n" + user_prompt

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


def aplicar(*, dictado, usuario):
    """Ejecuta las acciones `confirmada=True`. Una falla NO aborta el resto."""
    from .ejecutores import EJECUTORES

    if dictado.autor_id and dictado.autor_id != usuario.pk:
        raise PermissionError("Solo el autor puede aplicar su propio dictado.")

    acciones = list(dictado.acciones.filter(confirmada=True).order_by("orden"))
    aplicadas = 0
    fallidas = 0
    for accion in acciones:
        ejecutor = EJECUTORES.get(accion.tipo)
        if not ejecutor:
            accion.error_al_aplicar = f"Sin ejecutor para tipo `{accion.tipo}`."
            accion.save(update_fields=["error_al_aplicar"])
            fallidas += 1
            continue
        try:
            ejecutor(accion, usuario)
        except Exception as exc:  # noqa: BLE001
            accion.error_al_aplicar = str(exc)[:1000]
            accion.save(update_fields=["error_al_aplicar"])
            fallidas += 1
            continue
        accion.aplicada = True
        accion.aplicada_en = timezone.now()
        accion.save(update_fields=["aplicada", "aplicada_en", "entidad_tipo", "entidad_id"])
        aplicadas += 1

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
