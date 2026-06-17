"""Chat conversacional del Taller — loop de tool-use sobre `analizar()`.

Flujo de un turno (`conversar`):
1. Sanea el mensaje y lo persiste como MensajeChat(user).
2. Corre el loop: el LLM responde un sobre JSON (responder|herramienta|accion).
   - herramienta → ejecuta la función vetada, re-inyecta el resultado recortado
     y vuelve a llamar al LLM (cap `MAX_ITERACIONES`).
   - responder → persiste MensajeChat(bot, texto). Fin.
   - accion → crea Dictado(origen="taller_chat") + DictadoAccion (preview/confirm
     humano vía `services.aplicar`). Fin.
3. Caps de tokens: historial al LLM = últimos `MAX_TURNOS_PROMPT` turnos de
   texto/acción (NO los pasos de herramientas); resultados recortados; modelo
   barato (estación `taller_chat`).

Las consultas no escriben nada. Solo `accion` (confirmada por el usuario) muta
la DB, y lo hace por el flujo auditado de Dictado.
"""

from __future__ import annotations

import json
import logging

from django.db import transaction

from lib.analistas import PresupuestoIAExcedido

logger = logging.getLogger(__name__)

MAX_ITERACIONES = 4          # loop del modo texto (degradación)
MAX_ITERACIONES_TOOLS = 8    # loop del modo tool-use nativo (más cabeza)
MAX_TURNOS_PROMPT = 6
MAX_TITULO = 60

# Tools "especiales" del agente (no son consultas read-only del registry):
#  - proponer_acciones → crea un Dictado con preview/confirm humano.
#  - escalar_razonamiento → El Relevo: el agente se cambia a un modelo más fuerte.
TOOL_PROPONER = "proponer_acciones"
TOOL_ESCALAR = "escalar_razonamiento"

_SCHEMA_PROPONER = {
    "type": "object",
    "properties": {
        "texto": {"type": "string", "description": "Preámbulo humano breve para el usuario."},
        "acciones": {
            "type": "array",
            "description": "Lista de acciones propuestas (cada una con un tipo permitido).",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string", "description": "Uno de los tipos de acción permitidos."},
                    "descripcion": {"type": "string"},
                    "payload": {"type": "object"},
                    "confianza": {"type": "number"},
                },
                "required": ["tipo", "descripcion"],
            },
        },
    },
    "required": ["acciones"],
}

_SCHEMA_ESCALAR = {
    "type": "object",
    "properties": {"motivo": {"type": "string", "description": "Por qué la tarea necesita un modelo más potente."}},
    "required": ["motivo"],
}


def crear_conversacion(*, usuario, mensaje_inicial: str | None = None):
    """Crea una conversación vacía (el título se deriva del primer mensaje)."""
    from .models import ConversacionChat
    titulo = ""
    if mensaje_inicial:
        titulo = mensaje_inicial.strip().replace("\n", " ")[:MAX_TITULO]
    return ConversacionChat.objects.create(usuario=usuario, titulo=titulo)


def _historial_para_prompt(conversacion) -> list[dict]:
    """Últimos turnos de texto/acción (excluye tarjetas de herramienta)."""
    qs = (
        conversacion.mensajes
        .filter(tipo__in=("texto", "accion"))
        .order_by("-orden")[:MAX_TURNOS_PROMPT]
    )
    turnos = [{"rol": m.rol, "texto": m.cuerpo} for m in reversed(list(qs))]
    return turnos


def _siguiente_orden(conversacion) -> int:
    ultimo = conversacion.mensajes.order_by("-orden").values_list("orden", flat=True).first()
    return (ultimo or 0) + 1


def _crear_mensaje(conversacion, *, rol, tipo="texto", cuerpo="", nombre_herramienta="", dictado=None, chalan=""):
    from .models import MensajeChat
    return MensajeChat.objects.create(
        conversacion=conversacion,
        orden=_siguiente_orden(conversacion),
        rol=rol, tipo=tipo, cuerpo=cuerpo,
        nombre_herramienta=nombre_herramienta,
        dictado=dictado, chalan=chalan,
    )


def chat_acepta_imagenes(usuario=None) -> bool:
    """True si la estación `taller_chat` tiene algún Chalán con visión
    configurado — gobierna si el composer muestra el botón 📎."""
    try:
        from lib.analistas.capacidades import Capability
        from lib.analistas.registry import cadena_de
        cadena = cadena_de("taller_chat", usuario_id=getattr(usuario, "pk", None))
        return any(
            Capability.VISION in (a.capacidades or ()) and a.esta_configurado()
            for a in cadena
        )
    except Exception:  # noqa: BLE001 — sin DB/credenciales → sin botón
        return False


def _bloque_referencias(mensaje: str) -> str:
    """Resuelve los `@usuario/#proyecto/$cliente` del mensaje a entidades reales
    y arma un bloque para que el LLM sepa EXACTAMENTE a qué se refiere.

    Delega en `referencias.bloque.bloque_prompt` (fuente única, compartida con
    El Dictado estándar). Sin esto el modelo recibe `#exte` a secas y pide "el
    código (LC-0001)" aunque el usuario ya lo mencionó.
    """
    from referencias.bloque import bloque_prompt
    return bloque_prompt(mensaje)


def _persistir_adjunto_chat(mensaje, usuario, archivo) -> None:
    """Sube la imagen del turno a Drive (subcarpeta "El Chalán") y crea
    MensajeChatAdjunto. Fallback gracioso: si Drive cae, el chat ya respondió;
    el adjunto simplemente no queda en el historial."""
    if archivo is None:
        return
    import contextlib

    from lib.adjuntos import subir

    from .models import MensajeChatAdjunto
    with contextlib.suppress(Exception):
        archivo.seek(0)  # _imagenes_de_request ya lo leyó para el base64
    res = subir(archivo, subcarpeta="El Chalán")
    if res.ok and res.data:
        MensajeChatAdjunto.objects.create(
            mensaje=mensaje,
            drive_file_id=res.data["id"],
            nombre=res.data.get("name") or getattr(archivo, "name", "imagen"),
            mime_type=res.data.get("mimeType") or getattr(archivo, "content_type", "") or "",
            tamano_bytes=int(res.data.get("size") or getattr(archivo, "size", 0) or 0),
            subido_por=usuario,
        )


def _preparar_turno(*, mensaje, usuario, conversacion, imagenes, archivo_adjunto):
    """Saneo + persistencia del turno del usuario + historial. Común a ambos
    modos (nativo y texto). Devuelve `None` si no hay nada que procesar."""
    from lib.sanear import sanear_contexto
    mensaje = sanear_contexto((mensaje or "").strip(), max_len=4000)
    if not mensaje and not imagenes:
        return None
    if not mensaje and imagenes:  # imagen sin texto
        mensaje = "Lee esta imagen y dime qué información trae."

    cuerpo_user = mensaje + (" 📎 (imagen adjunta)" if imagenes else "")
    msg_user = _crear_mensaje(conversacion, rol="user", cuerpo=cuerpo_user)
    if archivo_adjunto is not None:
        _persistir_adjunto_chat(msg_user, usuario, archivo_adjunto)
    if not conversacion.titulo:
        conversacion.titulo = mensaje.replace("\n", " ")[:MAX_TITULO]
        conversacion.save(update_fields=["titulo"])

    historial = _historial_para_prompt(conversacion)
    # El último turno es el recién creado; lo quitamos (va aparte como mensaje nuevo).
    if historial and historial[-1]["rol"] == "user" and historial[-1]["texto"] == cuerpo_user:
        historial = historial[:-1]
    return {"mensaje": mensaje, "msg_user": msg_user, "historial": historial}


def _cadena_soporta_tools(usuario) -> bool:
    """True si la estación `taller_chat` tiene un Chalán con FUNCTION_CALLING
    configurado → usamos tool-use NATIVO. Si no, degradamos al protocolo de
    sobre-JSON sobre texto (comportamiento previo, sin regresión)."""
    try:
        from lib.analistas.capacidades import Capability
        from lib.analistas.registry import cadena_de
        cadena = cadena_de("taller_chat", usuario_id=getattr(usuario, "pk", None))
        return any(
            Capability.FUNCTION_CALLING in (a.capacidades or ()) and a.esta_configurado()
            for a in cadena
        )
    except Exception:  # noqa: BLE001
        return False


def conversar(*, mensaje: str, usuario, conversacion, imagenes: list | None = None,
              archivo_adjunto=None) -> dict:
    """Procesa un mensaje del usuario. Persiste turnos y devuelve los nuevos.

    Modo NATIVO (S-Chalan-Agente F1): function-calling real del proveedor +
    El Relevo (rutea el pensamiento al mejor modelo). Si la cadena no tiene un
    Chalán con FUNCTION_CALLING configurado, DEGRADA al protocolo de sobre-JSON
    sobre texto (comportamiento previo, sin regresión).

    `imagenes` (opcional): lista de dicts `{base64, media_type}` — van en el
    turno del usuario; El Reemplazo exige VISION cuando las hay.
    `archivo_adjunto` (opcional): UploadedFile para persistir la imagen en Drive.

    Nunca lanza. Retorna `{"mensajes": [MensajeChat, ...], "dictado": Dictado|None}`.
    """
    prep = _preparar_turno(
        mensaje=mensaje, usuario=usuario, conversacion=conversacion,
        imagenes=imagenes, archivo_adjunto=archivo_adjunto,
    )
    if prep is None:
        return {"mensajes": [], "dictado": None}
    if _cadena_soporta_tools(usuario):
        return _conversar_nativo(usuario=usuario, conversacion=conversacion, prep=prep, imagenes=imagenes)
    return _conversar_texto(usuario=usuario, conversacion=conversacion, prep=prep, imagenes=imagenes)


def _tool_specs(usuario) -> list[dict]:
    """Specs de herramientas para el modo nativo: las read-only del registry
    (filtradas por rol) + las 2 especiales del agente."""
    from .herramientas import herramientas_para
    specs = [
        {"nombre": h.nombre, "descripcion": h.descripcion, "args_schema": h.args_schema}
        for h in herramientas_para(usuario)
    ]
    specs.append({
        "nombre": TOOL_PROPONER,
        "descripcion": (
            "Propón cambios al sistema (crear/editar proyectos, tareas, recados, "
            "egresos, etc.). El usuario los revisa y confirma antes de aplicarse — "
            "tú solo propones, nunca se aplican solos. Usa SOLO los tipos de acción "
            "permitidos del system prompt."
        ),
        "json_schema": _SCHEMA_PROPONER,
    })
    specs.append({
        "nombre": TOOL_ESCALAR,
        "descripcion": (
            "El Relevo. Llama esto UNA vez cuando la tarea pida análisis, "
            "comparación, planeación o redacción cuidada, para pensar el resto con "
            "un modelo más potente. No lo uses para datos simples."
        ),
        "json_schema": _SCHEMA_ESCALAR,
    })
    return specs


def _mensajes_canonicos(usuario, historial, mensaje, imagenes) -> list[dict]:
    """Arma la conversación canónica para `chatear`: system + historial + turno
    nuevo del usuario (con el bloque de referencias @#$ resuelto)."""
    from .prompt_chat import construir_system_prompt_nativo
    msgs: list[dict] = [{"rol": "system", "texto": construir_system_prompt_nativo(usuario)}]
    for turno in (historial or []):
        rol = "user" if turno.get("rol") == "user" else "assistant"
        msgs.append({"rol": rol, "texto": turno.get("texto", "")})
    nuevo = {"rol": "user", "texto": mensaje + _bloque_referencias(mensaje)}
    if imagenes:
        nuevo["imagenes"] = imagenes
    msgs.append(nuevo)
    return msgs


def _conversar_nativo(*, usuario, conversacion, prep, imagenes) -> dict:
    """Loop de tool-use NATIVO con El Relevo (ruteo activo al mejor modelo)."""
    from lib.analistas import chatear, relevo

    from .herramientas import ejecutar_herramienta

    mensaje = prep["mensaje"]
    nuevos = [prep["msg_user"]]
    specs = _tool_specs(usuario)
    mensajes = _mensajes_canonicos(usuario, prep["historial"], mensaje, imagenes)

    estacion = relevo.estacion(relevo.nivel(mensaje))  # pre-ruteo heurístico ($0)
    chalan_provider = ""
    dictado_creado = None
    cerrado = False
    vistos: set[tuple] = set()
    pasos = 0

    for _ in range(MAX_ITERACIONES_TOOLS):
        try:
            res = chatear(
                estacion=estacion, mensajes=mensajes, herramientas=specs,
                max_tokens=900, temperatura=0.3, actor_id=getattr(usuario, "pk", None),
            )
        except PresupuestoIAExcedido as exc:
            nuevos.append(_crear_mensaje(conversacion, rol="bot", cuerpo=str(exc)))
            cerrado = True
            break
        except Exception as exc:  # noqa: BLE001 — TodosFallaron, red, etc.
            logger.warning("chat conv=%s tool-use falló: %s", conversacion.pk, exc)
            nuevos.append(_crear_mensaje(
                conversacion, rol="bot",
                cuerpo="Los Chalanes no están disponibles ahora mismo. Intenta de nuevo en un momento.",
            ))
            cerrado = True
            break

        chalan_provider = res.provider

        if not res.tool_calls:
            # Sin tool-calls → respuesta final del agente.
            nuevos.append(_crear_mensaje(
                conversacion, rol="bot", chalan=chalan_provider,
                cuerpo=(res.texto or "").strip() or "Listo.",
            ))
            cerrado = True
            break

        # Eco del turno assistant (con sus tool_calls) en la conversación canónica.
        mensajes.append({"rol": "assistant", "texto": res.texto or "", "tool_calls": list(res.tool_calls)})

        accion_tc = None
        for tc in res.tool_calls:
            if tc.nombre == TOOL_PROPONER:
                accion_tc = tc  # se procesa al final del turno (es terminal)
                continue
            if tc.nombre == TOOL_ESCALAR:
                estacion = relevo.ESTACION_PROFUNDA
                nuevos.append(_crear_mensaje(
                    conversacion, rol="bot", tipo="herramienta", chalan=chalan_provider,
                    nombre_herramienta="relevo", cuerpo=str(tc.args.get("motivo", "")),
                ))
                mensajes.append({"rol": "tool", "tool_call_id": tc.id, "nombre": tc.nombre,
                                 "texto": json.dumps({"ok": True, "nivel": "profundo"})})
                continue
            # Herramienta read-only del registry.
            clave = (tc.nombre, json.dumps(tc.args, sort_keys=True, default=str))
            if clave in vistos:
                salida = {"error": "consulta_repetida", "nota": "Ya consultaste esto; usa lo que tienes."}
            else:
                vistos.add(clave)
                salida = ejecutar_herramienta(tc.nombre, tc.args, usuario)
            nuevos.append(_crear_mensaje(
                conversacion, rol="bot", tipo="herramienta", chalan=chalan_provider,
                nombre_herramienta=tc.nombre, cuerpo=_resumen_herramienta(tc.nombre, salida),
            ))
            mensajes.append({"rol": "tool", "tool_call_id": tc.id, "nombre": tc.nombre,
                             "texto": json.dumps(salida, ensure_ascii=False, default=str)})
            pasos += 1

        if accion_tc is not None:
            args = accion_tc.args or {}
            dictado_creado = _persistir_acciones_chat(
                acciones_raw=args.get("acciones") or [], usuario=usuario, chalan=chalan_provider,
            )
            preambulo = (args.get("texto") or res.texto or "").strip()
            nuevos.append(_crear_mensaje(
                conversacion, rol="bot", tipo="accion", chalan=chalan_provider,
                cuerpo=preambulo or "Te propongo estas acciones. Revísalas y confírmalas.",
                dictado=dictado_creado,
            ))
            cerrado = True
            break

        # Re-ruteo: tras recabar varios datos, sube a profundo para sintetizar.
        if pasos >= 2 and estacion == relevo.ESTACION_RAPIDA:
            estacion = relevo.ESTACION_PROFUNDA

    if not cerrado:
        nuevos.append(_crear_mensaje(
            conversacion, rol="bot", chalan=chalan_provider,
            cuerpo="Consulté varias fuentes pero no pude cerrar la respuesta. Intenta una pregunta más específica.",
        ))

    conversacion.save(update_fields=["actualizado_en"])
    return {"mensajes": nuevos, "dictado": dictado_creado}


def _conversar_texto(*, usuario, conversacion, prep, imagenes) -> dict:
    """Loop de DEGRADACIÓN: protocolo de sobre-JSON sobre texto (comportamiento
    previo a S-Chalan-Agente, usado cuando ningún Chalán de la cadena soporta
    function-calling nativo)."""
    from .prompt_chat import (
        construir_prompt_con_resultado,
        construir_system_prompt,
        construir_user_prompt_chat,
    )
    from .services import _parsear_json  # heurística tolerante {…}

    mensaje = prep["mensaje"]
    historial = prep["historial"]
    nuevos = [prep["msg_user"]]

    system = construir_system_prompt(usuario)
    user_prompt = construir_user_prompt_chat(usuario=usuario, historial=historial, mensaje=mensaje)
    prompt_turno = system + "\n\n" + user_prompt + _bloque_referencias(mensaje)

    chalan_provider = ""
    vistos: set[tuple] = set()
    dictado_creado = None
    cerrado = False

    imgs_turno = imagenes or None  # solo en la primera llamada al LLM
    for _ in range(MAX_ITERACIONES):
        try:
            from lib.analistas import analizar
            res = analizar(
                estacion="taller_chat", prompt=prompt_turno,
                max_tokens=700, temperatura=0.3,
                actor_id=getattr(usuario, "pk", None),
                imagenes=imgs_turno,
            )
            imgs_turno = None  # las herramientas posteriores no re-envían la imagen
        except PresupuestoIAExcedido as exc:
            # El usuario alcanzó su tope de IA del mes (política `topar`).
            nuevos.append(_crear_mensaje(conversacion, rol="bot", cuerpo=str(exc)))
            cerrado = True
            break
        except Exception as exc:  # noqa: BLE001 — TodosFallaron, etc.
            logger.warning("chat conv=%s LLM falló: %s", conversacion.pk, exc)
            nuevos.append(_crear_mensaje(
                conversacion, rol="bot",
                cuerpo="Los Chalanes no están disponibles ahora mismo. Intenta de nuevo en un momento.",
            ))
            cerrado = True
            break

        chalan_provider = res.provider
        sobre = _parsear_sobre(res.texto, _parsear_json)
        if not isinstance(sobre, dict) or "tipo" not in sobre:
            nuevos.append(_crear_mensaje(
                conversacion, rol="bot", chalan=chalan_provider,
                cuerpo="No te entendí bien. ¿Puedes reformular la pregunta?",
            ))
            cerrado = True
            break

        tipo = sobre.get("tipo")
        if tipo == "responder":
            nuevos.append(_crear_mensaje(
                conversacion, rol="bot", chalan=chalan_provider,
                cuerpo=(sobre.get("texto") or "").strip() or "Listo.",
            ))
            cerrado = True
            break

        if tipo == "accion":
            acciones_raw = sobre.get("acciones") or []
            dictado_creado = _persistir_acciones_chat(acciones_raw=acciones_raw, usuario=usuario, chalan=chalan_provider)
            preambulo = (sobre.get("texto") or "").strip()
            nuevos.append(_crear_mensaje(
                conversacion, rol="bot", tipo="accion", chalan=chalan_provider,
                cuerpo=preambulo or "Te propongo estas acciones. Revísalas y confírmalas.",
                dictado=dictado_creado,
            ))
            cerrado = True
            break

        if tipo == "herramienta":
            nombre = (sobre.get("nombre") or "").strip()
            args = sobre.get("args") or {}
            clave = (nombre, json.dumps(args, sort_keys=True, default=str))
            if clave in vistos:
                # Dedup: el LLM repite la misma consulta → forzamos cierre.
                nuevos.append(_crear_mensaje(
                    conversacion, rol="bot", chalan=chalan_provider,
                    cuerpo="No pude cerrar la respuesta con la información disponible. Intenta una pregunta más específica.",
                ))
                cerrado = True
                break
            vistos.add(clave)
            from .herramientas import ejecutar_herramienta
            salida = ejecutar_herramienta(nombre, args, usuario)
            nuevos.append(_crear_mensaje(
                conversacion, rol="bot", tipo="herramienta", chalan=chalan_provider,
                nombre_herramienta=nombre,
                cuerpo=_resumen_herramienta(nombre, salida),
            ))
            prompt_turno = construir_prompt_con_resultado(prompt_turno, nombre, salida)
            continue

        # tipo desconocido → cierre suave
        nuevos.append(_crear_mensaje(
            conversacion, rol="bot", chalan=chalan_provider,
            cuerpo="No te entendí bien. ¿Puedes reformular la pregunta?",
        ))
        cerrado = True
        break

    if not cerrado:
        nuevos.append(_crear_mensaje(
            conversacion, rol="bot", chalan=chalan_provider,
            cuerpo="Consulté varias fuentes pero no pude cerrar la respuesta. Intenta una pregunta más específica.",
        ))

    conversacion.save(update_fields=["actualizado_en"])
    return {"mensajes": nuevos, "dictado": dictado_creado}


def _resumen_herramienta(nombre: str, salida) -> str:
    """Texto corto para la tarjeta informativa 🔧 (no es lo que ve el LLM)."""
    if isinstance(salida, dict) and salida.get("error"):
        return f"{nombre}: {salida.get('error')}"
    return nombre


def _persistir_acciones_chat(*, acciones_raw, usuario, chalan: str):
    """Crea un Dictado(origen='taller_chat') con las acciones propuestas.

    Filtra `TIPOS_PROHIBIDOS` (igual que `services.interpretar`). Las acciones
    quedan `confirmada=False` hasta que el usuario las marque en el preview —
    NUNCA se auto-aplican. Reusa los modelos auditados de El Dictado.
    """
    from .models import Dictado, DictadoAccion
    from .services import TIPOS_PROHIBIDOS, _apodo_de

    with transaction.atomic():
        dictado = Dictado.objects.create(
            autor=usuario,
            texto_crudo="(chat)",
            estado="esperando_confirmacion",
            origen="taller_chat",
            chalan=chalan,
            chalan_apodo=_apodo_de(chalan),
        )
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
            )
            orden += 1
    return dictado


def _parsear_sobre(texto: str, parser):
    """Parsea el sobre JSON con la heurística tolerante de El Dictado."""
    return parser(texto)
