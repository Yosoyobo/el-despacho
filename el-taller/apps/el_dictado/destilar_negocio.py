"""El Chalán APRENDE del negocio (S-Chalan-Negocio-V1).

A partir de los hechos reales del negocio (`taller_home.negocio`), destila
OBSERVACIONES DURABLES — patrones que seguirán siendo ciertos semanas/meses
("el cliente X paga tarde", "el margen de bordado es bajo", "las ventas caen
en julio") — y las propone como `ConocimientoNegocio` INACTIVO. El super_admin
las revisa/aprueba en La Gerencia; las aprobadas alimentan las opiniones del
Chalán (`conocimiento.bloque_contexto_negocio`).

Mismo patrón review-first y defensivo que el destilador de aprendizajes
(`destilar.py`). Reusa la estación `analisis_negocio`.
"""

from __future__ import annotations

import logging

from django.db import transaction

logger = logging.getLogger(__name__)

ESTACION = "analisis_negocio"
MAX_CANDIDATOS = 6
AMBITOS = ("finanzas", "cobranza", "ventas", "margenes")

_SYSTEM = """\
Eres El Chalán de El Despacho (Learning Center, diseño/maquila B2B). Tu trabajo
AHORA es APRENDER del negocio: de los HECHOS reales que te paso, destila
OBSERVACIONES DURABLES que te ayuden a asesorar mejor en el futuro.

Cada observación es un objeto:
  {"ambito": "finanzas|cobranza|ventas|margenes", "observacion": "...", "evidencia": "...", "peso": 1.0}

- `observacion`: un patrón del negocio que probablemente siga siendo cierto en
  semanas/meses (≤200 chars). Ej: "La cobranza acumula vencido >60 días — hay
  clientes que tardan en pagar", "El margen promedio del catálogo es bajo
  (~X%)", "El pipeline se concentra en 'por_cotizar' — faltan cierres".
- `evidencia`: 1 frase con el dato que la respalda.
- `peso`: 0.5 a 1.5 (1.0 normal; >1 si es claro y relevante).

REGLAS DURAS:
- SOLO patrones DURABLES y útiles. IGNORA cifras efímeras del día, y NO repitas
  ni reformules nada que ya esté en [CONOCIMIENTO YA REGISTRADO].
- NO inventes: básate solo en los hechos dados.
- Máximo 6 en total. Si no hay nada que de verdad valga la pena recordar,
  devuelve la lista vacía. Calidad sobre cantidad.

Devuelve SIEMPRE un ÚNICO objeto JSON, sin texto fuera del JSON:
{ "observaciones": [ { ... } ] }
"""


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _existentes() -> set[str]:
    from .models import ConocimientoNegocio
    return {_norm(o) for o in ConocimientoNegocio.objects.values_list("observacion", flat=True) if o}


def _construir_prompt(hechos: dict[str, dict], existentes: set[str]) -> str:
    from lib.sanear import sanear_contexto

    partes = [_SYSTEM, ""]
    if existentes:
        partes.append("[CONOCIMIENTO YA REGISTRADO — no lo repitas]")
        for o in sorted(existentes)[:60]:
            partes.append(f"- {o}")
        partes.append("")
    partes.append("[HECHOS DEL NEGOCIO]")
    for amb in AMBITOS:
        h = hechos.get(amb) or {}
        if h.get("hechos"):
            partes.append(f"\n## {amb} — {h['titulo']}")
            partes.append(h["hechos"])
    return sanear_contexto("\n".join(partes), max_len=12000)


def _llamar(prompt: str) -> dict:
    try:
        from lib.analistas import analizar
        res = analizar(estacion=ESTACION, prompt=prompt, max_tokens=1200,
                       temperatura=0.2, actor_id=None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("destilado de negocio: IA falló: %s", exc)
        return {"ok": False, "provider": "", "candidatos": [], "motivo": "fallo_ia"}
    from .services import _parsear_json
    parsed = _parsear_json(res.texto)
    if not isinstance(parsed, dict):
        return {"ok": False, "provider": res.provider, "candidatos": [], "motivo": "json_invalido"}
    cand = parsed.get("observaciones")
    if not isinstance(cand, list):
        cand = []
    return {"ok": True, "provider": res.provider, "candidatos": cand, "motivo": ""}


def _validar(crudos: list, existentes: set[str]) -> list[dict]:
    vistos = set(existentes)
    limpios: list[dict] = []
    for raw in crudos:
        if not isinstance(raw, dict):
            continue
        ambito = (raw.get("ambito") or "").strip()
        obs = (raw.get("observacion") or "").strip()[:400]
        if ambito not in AMBITOS or not obs:
            continue
        clave = _norm(obs)
        if clave in vistos:
            continue
        try:
            peso = float(raw.get("peso") or 1.0)
        except (TypeError, ValueError):
            peso = 1.0
        peso = max(0.3, min(3.0, peso))
        vistos.add(clave)
        limpios.append({
            "ambito": ambito, "observacion": obs,
            "evidencia": (raw.get("evidencia") or "").strip()[:1000],
            "peso": round(peso, 2),
        })
        if len(limpios) >= MAX_CANDIDATOS:
            break
    return limpios


def _persistir(candidatos: list[dict], *, creado_por) -> int:
    from .models import ConocimientoNegocio
    creados = 0
    with transaction.atomic():
        for c in candidatos:
            ConocimientoNegocio.objects.create(
                ambito=c["ambito"], observacion=c["observacion"],
                evidencia=c["evidencia"], peso=c["peso"],
                activo=False, origen="chalan_destilado", autor=creado_por,
            )
            creados += 1
    return creados


def destilar(*, dry_run: bool = False, creado_por=None) -> dict:
    """Destila conocimiento de negocio (review-first). Devuelve un resumen."""
    from apps.taller_home import negocio

    base = {"ok": True, "candidatos": [], "creados": 0, "dry_run": dry_run,
            "provider": "", "motivo": ""}

    hechos = negocio.todos_los_hechos()
    if not any(h.get("hechos") for h in hechos.values()):
        base["motivo"] = "sin_datos"
        return base

    existentes = _existentes()
    ia = _llamar(_construir_prompt(hechos, existentes))
    base["provider"] = ia["provider"]
    if not ia["ok"]:
        base["ok"], base["motivo"] = False, ia["motivo"]
        return base

    candidatos = _validar(ia["candidatos"], existentes)
    base["candidatos"] = candidatos
    if dry_run or not candidatos:
        base["motivo"] = "dry_run" if dry_run else ("sin_candidatos" if not candidatos else "")
        return base

    base["creados"] = _persistir(candidatos, creado_por=creado_por)
    _emitir(base["creados"], ia["provider"])
    return base


def _emitir(creados: int, provider: str) -> None:
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="chalan.conocimiento_destilado",  # type: ignore[arg-type]
            actor_id=None, actor_email=None,
            payload={"creados": creados, "provider": provider},
        ))
    except Exception:  # noqa: BLE001
        logger.warning("emitir chalan.conocimiento_destilado falló", exc_info=True)
