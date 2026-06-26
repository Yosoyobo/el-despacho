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

Te paso ejemplos reales de dictados que ya interpretaste, marcando dónde el
usuario te CORRIGIÓ (sus clarificaciones) o DESMARCÓ acciones que propusiste
mal. De ahí destila APRENDIZAJES reutilizables: jerga, abreviaturas o atajos
del despacho y a qué entidad/acción corresponden de verdad.

Cada aprendizaje es un objeto:
  {"frase_o_patron": "...", "interpretacion_correcta": "...", "peso": 1.0, "razon": "..."}

- `frase_o_patron`: la frase/jerga ambigua tal como la dice el equipo, corta
  (≤120 chars). Ej: "la heladería", "lo de siempre de Pérez", "manda al chofer".
- `interpretacion_correcta`: qué debe entender el Chalán al verla — la entidad
  o acción concreta y reutilizable. Ej: "$heladeria-michoacana (cliente)",
  "asignar tipo=recoger al runner más cercano".
- `peso`: 0.5 a 1.5 (1.0 normal; >1 si el patrón es muy claro y se repite).
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

    con_senal: list[Dictado] = []
    sin_senal: list[Dictado] = []
    for d in qs[: max(limite * 3, 30)]:
        tiene_clarif = bool(d.historial_clarificaciones)
        tiene_desmarque = d.estado == "confirmado_parcial"
        (con_senal if (tiene_clarif or tiene_desmarque) else sin_senal).append(d)

    elegidos = (con_senal + sin_senal)[:limite]
    if not elegidos:
        return []

    # Acciones desmarcadas (confirmada=False) en un solo query.
    desmarcadas: dict[int, list[str]] = {}
    ids = [d.pk for d in elegidos]
    for a in DictadoAccion.objects.filter(dictado_id__in=ids, confirmada=False):
        desmarcadas.setdefault(a.dictado_id, []).append(f"{a.tipo}: {a.descripcion}")

    evidencia: list[dict[str, Any]] = []
    for d in elegidos:
        evidencia.append({
            "id": d.pk,
            "texto": (d.texto_crudo or "").strip()[:600],
            "interpretacion": _resumen_interpretacion(d),
            "clarificaciones": _resumen_clarificaciones(d),
            "desmarcadas": desmarcadas.get(d.pk, []),
        })
    return evidencia


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


def _construir_prompt(evidencia: list[dict[str, Any]], existentes: set[str]) -> str:
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
        vistos.add(clave)
        limpios.append({
            "frase_o_patron": frase,
            "interpretacion_correcta": interp,
            "peso": round(peso, 2),
            "razon": (raw.get("razon") or "").strip()[:300],
        })
        if len(limpios) >= MAX_CANDIDATOS:
            break
    return limpios


# ── Persistencia ─────────────────────────────────────────────────────


def _persistir(candidatos: list[dict[str, Any]], *, creado_por) -> int:
    from chalanes.models import Aprendizaje

    creados = 0
    with transaction.atomic():
        for c in candidatos:
            Aprendizaje.objects.create(
                frase_o_patron=c["frase_o_patron"],
                interpretacion_correcta=c["interpretacion_correcta"],
                peso=c["peso"],
                activo=False,            # nace inactivo — se revisa en Gerencia
                origen="chalan_destilado",
                autor=creado_por,
            )
            creados += 1
    return creados


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
            "dry_run": dry_run, "provider": "", "motivo": ""}

    evidencia = recolectar_evidencia(dias=dias, limite=limite)
    base["analizados"] = len(evidencia)
    if not evidencia:
        base["motivo"] = "sin_evidencia"
        return base

    existentes = _frases_existentes()
    prompt = _construir_prompt(evidencia, existentes)
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

    creados = _persistir(candidatos, creado_por=creado_por)
    base["creados"] = creados
    _emitir(creado_por=creado_por, creados=creados, analizados=len(evidencia),
            provider=ia["provider"])
    return base
