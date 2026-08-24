"""Hablarle a n8n desde El Despacho — para que El Chalán pueda mirar y proponer.

n8n es donde viven las tareas que corren solas: leer el buzón de facturas,
avisar cuando algo se atrasa, lo que se vaya sumando. El equipo no sabe usarlo
y Oscar fue explícito desde el principio: tiene que estar **súper asistido por
el Chalán**, con *muchos guardrails*.

**Qué puede hacer El Chalán y qué no.** Leer, todo: qué flujos hay, cuáles
están prendidos, qué corrió anoche y qué falló. Escribir, nada por su cuenta:
prender, apagar, crear o borrar un flujo pasa por el camino de siempre —
propone, un humano confirma (§20).

Y no es celo de más. Un flujo prendido **le manda correos a clientes**: que un
modelo pueda activarlo sin que nadie lo vea sería regalarle la voz del despacho.

**La llave.** La API de n8n pide una `X-N8N-API-KEY` que se genera dentro de
n8n (Configuración → API). Se guarda en La Bóveda, como toda credencial del
repo (§4 #3). Sin llave, todo esto se apaga solo: `disponible()` da False y las
capacidades desaparecen del catálogo del Chalán en vez de fallar cuando las use.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get("N8N_URL", "http://n8n:5678")
SLOT_LLAVE = "n8n_api_key"
ENV_LLAVE = "N8N_API_KEY"
CABECERA = "X-N8N-API-KEY"

TIMEOUT = 8.0

#: Tope de lo que se le entrega al modelo de una vez. Un despacho no va a tener
#: cien flujos, y una lista larga sólo sirve para gastar contexto.
TOPE = 25


def llave() -> str:
    """La llave de la API, de La Bóveda o del entorno. Vacía = no configurada."""
    try:
        from ajustes.models.credencial import Credencial

        v = (Credencial.obtener(SLOT_LLAVE) or "").strip()
        if v:
            return v
    except Exception:  # noqa: BLE001 — sin base, queda la del entorno
        pass
    return (os.environ.get(ENV_LLAVE) or "").strip()


def esta_configurado() -> bool:
    return bool(llave())


def _pedir(ruta: str, *, metodo: str = "GET", cuerpo: dict | None = None) -> Any:
    """Llama a la API. Devuelve el JSON, o None si algo salió mal.

    Nunca lanza: quien llama es una capacidad del Chalán, y una traza no le
    sirve de nada al modelo ni a quien está leyendo la conversación.
    """
    k = llave()
    if not k:
        return None
    try:
        import urllib.request

        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1{ruta}", data=datos, method=metodo,
            headers={CABECERA: k, "Content-Type": "application/json",
                     "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            crudo = r.read()
            return json.loads(crudo) if crudo else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n: %s %s falló: %s", metodo, ruta, exc)
        return None


def disponible() -> bool:
    """¿Hay llave Y contesta la API?"""
    return _pedir("/workflows?limit=1") is not None


# ── Leer ───────────────────────────────────────────────────────────────────


def _resumir(w: dict) -> dict:
    """Un flujo, en lo que de verdad importa saber de él."""
    nodos = w.get("nodes") or []
    return {
        "id": str(w.get("id", "")),
        "nombre": w.get("name") or "(sin nombre)",
        "activo": bool(w.get("active")),
        "pasos": len(nodos),
        # Qué lo dispara es la pregunta que uno hace primero: un flujo que
        # arranca solo no es lo mismo que uno que espera a que lo llamen.
        "disparador": next(
            (n.get("name") or n.get("type", "").rsplit(".", 1)[-1]
             for n in nodos
             if "trigger" in (n.get("type") or "").lower()),
            "manual",
        ),
        "actualizado": (w.get("updatedAt") or "")[:10],
    }


def listar_flujos() -> list[dict] | None:
    datos = _pedir(f"/workflows?limit={TOPE}")
    if datos is None:
        return None
    return [_resumir(w) for w in (datos.get("data") or [])]


def detalle_flujo(flujo_id: str) -> dict | None:
    w = _pedir(f"/workflows/{flujo_id}")
    if w is None:
        return None
    resumen = _resumir(w)
    resumen["nodos"] = [
        {"nombre": n.get("name"), "tipo": (n.get("type") or "").rsplit(".", 1)[-1]}
        for n in (w.get("nodes") or [])[:30]
    ]
    return resumen


def ejecuciones(flujo_id: str | None = None, limite: int = 10) -> list[dict] | None:
    """Las últimas corridas. Sin `flujo_id`, de todos."""
    ruta = f"/executions?limit={min(limite, TOPE)}"
    if flujo_id:
        ruta += f"&workflowId={flujo_id}"
    datos = _pedir(ruta)
    if datos is None:
        return None
    return [{
        "id": str(e.get("id", "")),
        "flujo": (e.get("workflowData") or {}).get("name") or str(e.get("workflowId", "")),
        "estado": e.get("status") or ("ok" if e.get("finished") else "?"),
        "cuando": (e.get("startedAt") or "")[:16].replace("T", " "),
    } for e in (datos.get("data") or [])]


# ── Escribir — sólo desde un ejecutor, tras confirmación humana ────────────


def activar(flujo_id: str) -> bool:
    return _pedir(f"/workflows/{flujo_id}/activate", metodo="POST") is not None


def desactivar(flujo_id: str) -> bool:
    return _pedir(f"/workflows/{flujo_id}/deactivate", metodo="POST") is not None


def borrar(flujo_id: str) -> bool:
    return _pedir(f"/workflows/{flujo_id}", metodo="DELETE") is not None


def crear(nombre: str, nodos: list[dict], conexiones: dict | None = None) -> dict | None:
    """Crea un flujo APAGADO. Siempre apagado, sin excepción.

    Un flujo nuevo que arranca solo puede mandar correos a clientes desde el
    primer minuto, antes de que nadie lo haya visto funcionar. Se crea, se
    revisa en n8n, y se prende a mano.
    """
    cuerpo = {
        "name": nombre[:120],
        "nodes": nodos,
        "connections": conexiones or {},
        "settings": {},
    }
    w = _pedir("/workflows", metodo="POST", cuerpo=cuerpo)
    return _resumir(w) if w else None


__all__ = [
    "BASE_URL",
    "CABECERA",
    "ENV_LLAVE",
    "SLOT_LLAVE",
    "TOPE",
    "activar",
    "borrar",
    "crear",
    "desactivar",
    "detalle_flujo",
    "disponible",
    "ejecuciones",
    "esta_configurado",
    "listar_flujos",
    "llave",
]
