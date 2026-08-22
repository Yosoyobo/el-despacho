"""El Chalán que aprende de lo que ve — destilador de aprendizajes (compartido).

Lee el historial reciente de Dictados — sobre todo las señales de CORRECCIÓN
(clarificaciones donde el usuario reorientó al Chalán, y acciones que el
usuario DESMARCÓ antes de aplicar) — y le pide al propio Chalán que destile
APRENDIZAJES reutilizables (frase → interpretación correcta).

**Vive en la app compartida `chalanes/`** (no en `apps.el_dictado`, que solo
existe en El Taller) para que lo puedan disparar DOS surfaces:

- El Taller: el cron semanal `chalan_destilar_aprendizajes` (back-office).
- La Gerencia: el botón "barrido" en Chalanes → Aprendizajes ("forzar ahora").

Lee/escribe vía los shadow models `managed=False` de `chalanes.models`
(`Dictado`, `DictadoAccion`, `Aprendizaje`) — todos apuntan a las tablas
`el_dictado_*` de la única Postgres. NO importa nada de `apps.el_dictado`,
así corre idéntico en ambos proyectos Django.

Diseño:
- **Propone, no actúa**: los aprendizajes se crean INACTIVOS
  (`activo=False`, `origen='chalan_destilado'`). El super_admin los revisa en
  La Gerencia → Chalanes → Aprendizajes y activa los buenos con un clic. NO
  afectan el prompt del Dictado hasta que se activan.
- **Una sola llamada IA**: la evidencia ya viene de la DB; el Chalán solo la
  sintetiza. Barato y determinista (sin loop de herramientas).
- **Dedup por frase**: no re-propone una frase que ya existe (activa o no),
  así que descartar (dejar inactivo) un candidato basta para que no vuelva en
  la siguiente corrida.
- **Defensivo**: si la IA cae o el usuario está topado, no crea nada y
  devuelve un resumen — nunca lanza.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

ESTACION = "aprendizaje_destilado"
MAX_CANDIDATOS = 8

_SYSTEM = """\
Eres El Chalán de El Despacho (CRM/ERP de Learning Center, diseño/maquila B2B
mexicano). Tu trabajo AHORA no es interpretar un dictado nuevo: es APRENDER de
tu propio historial para interpretar MEJOR la próxima vez.

Te paso evidencia real de cuatro fuentes:
- Dictados donde el usuario te CORRIGIÓ o DESMARCÓ lo que propusiste.
- Dictados que FALLARON o se aplicaron con errores (ahí no entendiste algo).
- Conversaciones del chat: cómo te habla el equipo de verdad.
- El error concreto que devolvió el sistema al intentar aplicar la acción.

De ahí destila APRENDIZAJES reutilizables: jerga, abreviaturas o atajos del
despacho y a qué entidad/acción corresponden de verdad.

Cada aprendizaje es un objeto:
  {"frase_o_patron": "...", "interpretacion_correcta": "...", "peso": 1.0,
   "confianza": 0.9, "razon": "..."}

- `frase_o_patron`: la frase/jerga ambigua tal como la dice el equipo, corta
  (≤120 chars). Ej: "la heladería", "lo de siempre de Pérez", "manda al chofer".
- `interpretacion_correcta`: qué debe entender el Chalán al verla — la entidad
  o acción concreta y reutilizable. Ej: "$heladeria-michoacana (cliente)",
  "asignar tipo=recoger al runner más cercano".
- `peso`: 0.5 a 1.5 (1.0 normal; >1 si el patrón es muy claro y se repite).
- `confianza`: 0 a 1 — qué tan seguro estás de que este patrón es real y
  reutilizable. Usa 0.9 o más SÓLO cuando la evidencia lo muestre repetido y
  sin ambigüedad; si es una corazonada de un solo caso, 0.5 o menos. Los de
  confianza muy alta pueden activarse sin que nadie los revise, así que no
  infles el número.
- `razon`: 1 frase de la evidencia que lo respalda.

REGLAS DURAS:
- SOLO patrones DURABLES y reutilizables. Ignora errores de dedo, datos de un
  caso único, nombres propios irrepetibles, o cualquier cosa que YA esté en
  [APRENDIZAJES EXISTENTES] (no los repitas ni reformules).
- NO inventes: básate ÚNICAMENTE en la evidencia que te doy.
- Máximo 8. Si no hay nada que de verdad valga la pena aprender, devuelve la
  lista vacía. Calidad sobre cantidad.

Devuelve SIEMPRE un ÚNICO objeto JSON, sin texto fuera del JSON:
{ "aprendizajes": [ { ... } ] }
"""


# ── Recolección de evidencia ─────────────────────────────────────────


def recolectar_evidencia(*, dias: int = 30, limite: int = 60) -> list[dict[str, Any]]:
    """Reúne dictados recientes priorizando señales de corrección.

    Una "señal" es un dictado donde el usuario clarificó (lo reorientó) o
    desmarcó alguna acción (estado `confirmado_parcial`). Esos van primero;
    el resto rellena hasta `limite` para dar contexto de patrones comunes.
    """
    from chalanes.models import Dictado, DictadoAccion

    desde = timezone.now() - timedelta(days=dias)
    qs = (
        Dictado.objects.filter(creado_en__gte=desde, autor__isnull=False)
        .exclude(texto_crudo="")
        .order_by("-creado_en")
    )

    # Qué cuenta como señal de que el Chalán se equivocó. Las correcciones
    # explícitas son la mejor evidencia, pero son rarísimas: en tres meses de
    # uso real hubo 8. Los dictados que reventaron o se aplicaron a medias son
    # 85, y son exactamente los casos donde no entendió. Ignorarlos era mirar
    # la señal escasa y desperdiciar la abundante.
    ESTADOS_FALLIDOS = {"fallo_ia", "aplicado_con_errores", "cancelado"}

    con_senal: list[Dictado] = []
    sin_senal: list[Dictado] = []
    for d in qs[: max(limite * 3, 30)]:
        tiene_clarif = bool(d.historial_clarificaciones)
        tiene_desmarque = d.estado == "confirmado_parcial"
        fallo = d.estado in ESTADOS_FALLIDOS
        (con_senal if (tiene_clarif or tiene_desmarque or fallo) else sin_senal).append(d)

    elegidos = (con_senal + sin_senal)[:limite]
    if not elegidos:
        return []

    # Acciones desmarcadas (confirmada=False) en un solo query.
    desmarcadas: dict[int, list[str]] = {}
    ids = [d.pk for d in elegidos]
    for a in DictadoAccion.objects.filter(dictado_id__in=ids, confirmada=False):
        desmarcadas.setdefault(a.dictado_id, []).append(f"{a.tipo}: {a.descripcion}")

    # Por qué falló cada acción, cuando falló.
    errores: dict[int, list[str]] = {}
    for a in DictadoAccion.objects.filter(dictado_id__in=ids).exclude(error_al_aplicar=""):
        errores.setdefault(a.dictado_id, []).append(
            f"{a.tipo}: {(a.error_al_aplicar or '')[:120]}"
        )

    evidencia: list[dict[str, Any]] = []
    for d in elegidos:
        evidencia.append({
            "id": d.pk,
            "texto": (d.texto_crudo or "").strip()[:600],
            "interpretacion": _resumen_interpretacion(d),
            "clarificaciones": _resumen_clarificaciones(d),
            "desmarcadas": desmarcadas.get(d.pk, []),
            "estado": d.estado,
            "errores": errores.get(d.pk, []),
        })
    return evidencia


def recolectar_conversaciones(*, dias: int = 30, limite: int = 40) -> list[dict[str, Any]]:
    """Turnos del chat donde se ve cómo le habla el equipo al Chalán.

    Es la fuente más abundante que hay: los dictados se cuentan por decenas y
    los mensajes del chat por miles. Se toman los pares «lo que dijo la persona
    → lo que contestó el Chalán» de las conversaciones recientes.
    """
    from chalanes.models import MensajeChat

    desde = timezone.now() - timedelta(days=dias)
    try:
        mensajes = list(
            MensajeChat.objects.filter(creado_en__gte=desde)
            .exclude(cuerpo="")
            .order_by("conversacion_id", "orden")[: limite * 6]
        )
    except Exception:  # noqa: BLE001
        logger.warning("no se pudieron leer las conversaciones del chat", exc_info=True)
        return []

    pares: list[dict[str, Any]] = []
    pendiente: str | None = None
    conversacion_actual = None
    for m in mensajes:
        if m.conversacion_id != conversacion_actual:
            conversacion_actual, pendiente = m.conversacion_id, None
        if m.rol == "usuario":
            pendiente = (m.cuerpo or "").strip()[:400]
        elif pendiente and m.rol in ("asistente", "bot", "chalan"):
            pares.append({
                "id": m.pk,
                "pregunta": pendiente,
                "respuesta": (m.cuerpo or "").strip()[:300],
            })
            pendiente = None
        if len(pares) >= limite:
            break
    return pares


def _resumen_interpretacion(dictado) -> str:
    """Texto corto de cómo el Chalán entendió el dictado (acciones propuestas)."""
    raw = dictado.interpretacion_raw or {}
    acciones = raw.get("acciones") if isinstance(raw, dict) else None
    if not isinstance(acciones, list) or not acciones:
        return ""
    partes = []
    for a in acciones[:6]:
        if isinstance(a, dict):
            partes.append(f"{a.get('tipo', '?')}: {a.get('descripcion', '')}".strip())
    return " | ".join(p for p in partes if p)


def _resumen_clarificaciones(dictado) -> list[str]:
    out = []
    for turno in (dictado.historial_clarificaciones or [])[:4]:
        if isinstance(turno, dict):
            p = (turno.get("pregunta") or "").strip()
            r = (turno.get("respuesta") or "").strip()
            if r:
                out.append(f"Chalán preguntó «{p}» → usuario corrigió «{r}»")
    return out


# ── Prompt ───────────────────────────────────────────────────────────


def _frases_existentes() -> set[str]:
    from chalanes.models import Aprendizaje
    return {
        _norm(f)
        for f in Aprendizaje.objects.values_list("frase_o_patron", flat=True)
        if f
    }


def _norm(frase: str) -> str:
    return " ".join((frase or "").lower().split())


def _construir_prompt(
    evidencia: list[dict[str, Any]],
    existentes: set[str],
    conversaciones: list[dict[str, Any]] | None = None,
) -> str:
    from lib.sanear import sanear_contexto

    partes = [_SYSTEM, ""]
    if existentes:
        partes.append("[APRENDIZAJES EXISTENTES — no los repitas]")
        for f in sorted(existentes)[:60]:
            partes.append(f"- {f}")
        partes.append("")

    partes.append("[EVIDENCIA — dictados recientes y cómo los interpretaste]")
    for i, ev in enumerate(evidencia, 1):
        partes.append(f"\n#{i} (dictado {ev['id']})")
        partes.append(f"  Usuario dijo: {ev['texto']}")
        if ev["interpretacion"]:
            partes.append(f"  Chalán entendió: {ev['interpretacion']}")
        for c in ev["clarificaciones"]:
            partes.append(f"  CORRECCIÓN: {c}")
        for dm in ev["desmarcadas"]:
            partes.append(f"  DESMARCADA (propuesta rechazada por el usuario): {dm}")
        if ev.get("estado") in ("fallo_ia", "aplicado_con_errores", "cancelado"):
            partes.append(f"  RESULTADO: {ev['estado']} — aquí algo no se entendió.")
        for err in ev.get("errores", [])[:3]:
            partes.append(f"  ERROR AL APLICAR: {err}")

    if conversaciones:
        partes.append("")
        partes.append("[CONVERSACIONES — cómo te habla el equipo en el chat]")
        for i, c in enumerate(conversaciones, 1):
            partes.append(f"\n·{i} Persona: {c['pregunta']}")
            if c.get("respuesta"):
                partes.append(f"   Tú: {c['respuesta']}")

    texto = "\n".join(partes)
    return sanear_contexto(texto, max_len=12000)


# ── Llamada al Chalán + parseo ───────────────────────────────────────


def _parsear_json(texto: str):
    """Parsea JSON; si el LLM mete texto antes/después, extrae el primer {...}."""
    if not texto:
        return None
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio < 0 or fin < inicio:
        return None
    try:
        return json.loads(texto[inicio : fin + 1])
    except json.JSONDecodeError:
        return None


def _llamar_chalan(prompt: str, creado_por) -> dict[str, Any]:
    """Una llamada a El Chalán → `{ok, provider, candidatos, motivo}`. Nunca lanza."""
    try:
        from lib.analistas import PresupuestoIAExcedido, analizar
        try:
            res = analizar(
                estacion=ESTACION, prompt=prompt,
                max_tokens=1400, temperatura=0.2,
                actor_id=getattr(creado_por, "pk", None),
            )
        except PresupuestoIAExcedido:
            return {"ok": False, "provider": "", "candidatos": [], "motivo": "presupuesto_topado"}
    except Exception as exc:  # noqa: BLE001 — TodosFallaron, red, etc.
        logger.warning("destilado de aprendizajes: IA falló: %s", exc)
        return {"ok": False, "provider": "", "candidatos": [], "motivo": "fallo_ia"}

    parsed = _parsear_json(res.texto)
    if not isinstance(parsed, dict):
        return {"ok": False, "provider": res.provider, "candidatos": [], "motivo": "json_invalido"}
    cand = parsed.get("aprendizajes")
    if not isinstance(cand, list):
        cand = []
    return {"ok": True, "provider": res.provider, "candidatos": cand, "motivo": ""}


def _validar_candidatos(crudos: list, existentes: set[str]) -> list[dict[str, Any]]:
    """Limpia y deduplica. Descarta lo que ya existe o repite dentro del lote."""
    vistos = set(existentes)
    limpios: list[dict[str, Any]] = []
    for raw in crudos:
        if not isinstance(raw, dict):
            continue
        frase = (raw.get("frase_o_patron") or "").strip()[:300]
        interp = (raw.get("interpretacion_correcta") or "").strip()
        if not frase or not interp:
            continue
        clave = _norm(frase)
        if clave in vistos:
            continue
        try:
            peso = float(raw.get("peso") or 1.0)
        except (TypeError, ValueError):
            peso = 1.0
        peso = max(0.3, min(3.0, peso))
        try:
            confianza = float(raw.get("confianza") if raw.get("confianza") is not None else 0.5)
        except (TypeError, ValueError):
            confianza = 0.5
        confianza = max(0.0, min(1.0, confianza))
        vistos.add(clave)
        limpios.append({
            "frase_o_patron": frase,
            "interpretacion_correcta": interp,
            "peso": round(peso, 2),
            "confianza": round(confianza, 2),
            "razon": (raw.get("razon") or "").strip()[:300],
        })
        if len(limpios) >= MAX_CANDIDATOS:
            break
    return limpios


# ── Persistencia ─────────────────────────────────────────────────────


def _politica_auto() -> tuple[bool, float]:
    """¿Puede activar solo lo que aprende, y con cuánta seguridad? (Gerencia)."""
    try:
        from ajustes.models import ConfiguracionAnalisis

        cfg = ConfiguracionAnalisis.obtener()
        return bool(cfg.auto_activar_aprendizajes), float(cfg.confianza_minima_auto)
    except Exception:  # noqa: BLE001
        return False, 1.0  # ante la duda, que lo revise una persona


def _persistir(candidatos: list[dict[str, Any]], *, creado_por) -> tuple[int, int]:
    """Guarda los aprendizajes. Devuelve (creados, activados solos).

    Los que el Chalán marca con confianza muy alta se activan solos si así se
    configuró en Gerencia; el resto espera revisión. Sea como sea, quedan a la
    vista y se apagan con un clic. Y nada de esto ejecuta acciones: sólo
    cambia cómo INTERPRETA lo que le dicen.
    """
    from chalanes.models import Aprendizaje

    auto, umbral = _politica_auto()
    creados = activados = 0
    with transaction.atomic():
        for c in candidatos:
            solo = auto and c.get("confianza", 0) >= umbral
            Aprendizaje.objects.create(
                frase_o_patron=c["frase_o_patron"],
                interpretacion_correcta=c["interpretacion_correcta"],
                peso=c["peso"],
                activo=solo,
                origen="chalan_destilado",
                autor=creado_por,
            )
            creados += 1
            activados += 1 if solo else 0
    if activados:
        _emitir_auto(activados, creado_por)
    return creados, activados


def _emitir_auto(activados: int, creado_por) -> None:
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz

        emitir(EventoPortavoz(
            tipo="chalan.aprendizaje_auto_activado",  # type: ignore[arg-type]
            actor_id=getattr(creado_por, "pk", None),
            actor_email=getattr(creado_por, "email", None),
            payload={"activados": activados},
        ))
    except Exception:  # noqa: BLE001
        pass


def _emitir(*, creado_por, creados: int, analizados: int, provider: str) -> None:
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="chalan.aprendizaje_destilado",  # type: ignore[arg-type]
            actor_id=getattr(creado_por, "pk", None),
            actor_email=getattr(creado_por, "email", None),
            payload={"creados": creados, "analizados": analizados, "provider": provider},
        ))
    except Exception:  # noqa: BLE001
        logger.warning("emitir chalan.aprendizaje_destilado falló", exc_info=True)


# ── Orquestador ──────────────────────────────────────────────────────


def destilar_aprendizajes(
    *, dias: int = 30, limite: int = 60, dry_run: bool = False, creado_por=None,
) -> dict[str, Any]:
    """Destila aprendizajes del historial reciente. Devuelve un resumen.

    Forma del resultado:
      {ok, analizados, candidatos: [...], creados, dry_run, provider, motivo}

    `candidatos` siempre trae los que pasaron validación/dedup (con `razon`),
    aunque `dry_run=True` (no se persiste) o `creados=0`.
    """
    base = {"ok": True, "analizados": 0, "candidatos": [], "creados": 0,
            "activados": 0, "conversaciones": 0,
            "dry_run": dry_run, "provider": "", "motivo": ""}

    evidencia = recolectar_evidencia(dias=dias, limite=limite)
    conversaciones = recolectar_conversaciones(dias=dias)
    base["analizados"] = len(evidencia)
    base["conversaciones"] = len(conversaciones)
    if not evidencia and not conversaciones:
        base["motivo"] = "sin_evidencia"
        return base

    existentes = _frases_existentes()
    prompt = _construir_prompt(evidencia, existentes, conversaciones)
    ia = _llamar_chalan(prompt, creado_por)
    base["provider"] = ia["provider"]
    if not ia["ok"]:
        base["ok"] = False
        base["motivo"] = ia["motivo"]
        return base

    candidatos = _validar_candidatos(ia["candidatos"], existentes)
    base["candidatos"] = candidatos
    if dry_run or not candidatos:
        base["motivo"] = "dry_run" if dry_run else ("sin_candidatos" if not candidatos else "")
        return base

    creados, activados = _persistir(candidatos, creado_por=creado_por)
    base["creados"] = creados
    base["activados"] = activados
    _emitir(creado_por=creado_por, creados=creados, analizados=len(evidencia),
            provider=ia["provider"])
    return base
