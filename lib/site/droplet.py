"""DigitalOcean — info del Droplet (specs y bandwidth del mes).

Necesita la credencial `do_api_token` cifrada en Los Ajustes. Si no hay
token configurado, retorna `disponible=False, motivo="no_configurada"`.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

API = "https://api.digitalocean.com/v2"
TIMEOUT = 8.0


def _token() -> str | None:
    try:
        from ajustes.models.credencial import Credencial
        return Credencial.obtener("do_api_token")
    except Exception:
        return None


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def chequear() -> dict[str, Any]:
    """GET /v2/account — prueba que el token sirva. Devuelve estado para
    la batería de integraciones (`integraciones.py`)."""
    tok = _token()
    if not tok:
        return {"estado": "no_configurada", "motivo": "do_api_token no configurado"}
    t0 = time.monotonic()
    try:
        r = httpx.get(f"{API}/account", headers=_headers(tok), timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        return {"estado": "error", "mensaje_error": str(exc)[:200], "latencia_ms": int((time.monotonic() - t0) * 1000)}
    latencia = int((time.monotonic() - t0) * 1000)
    if r.status_code != 200:
        return {"estado": "error", "mensaje_error": f"HTTP {r.status_code}", "latencia_ms": latencia}
    return {"estado": "ok", "latencia_ms": latencia}


def info_local() -> dict[str, Any]:
    """Info estática que NO requiere DO API: nombre lógico + IP visible.
    Usado en el cuadrante de Infraestructura aunque no haya token."""
    return {"nombre_logico": "la-sede", "ip_publica_esperada": "157.230.48.232"}


def info_remota(droplet_id: int | None = None) -> dict[str, Any]:
    """Specs reales del Droplet + bandwidth del mes en curso. Requiere
    `do_api_token`. Si no hay token o no se encuentra el Droplet, retorna
    `disponible=False`."""
    tok = _token()
    if not tok:
        return {"disponible": False, "motivo": "no_configurada"}
    try:
        if droplet_id is None:
            r = httpx.get(f"{API}/droplets", headers=_headers(tok), timeout=TIMEOUT)
            if r.status_code != 200:
                return {"disponible": False, "motivo": f"HTTP {r.status_code}"}
            droplets = (r.json() or {}).get("droplets") or []
            objetivo = next(
                (d for d in droplets if "157.230.48.232" in [n.get("ip_address") for n in d.get("networks", {}).get("v4", [])]),
                droplets[0] if droplets else None,
            )
            if not objetivo:
                return {"disponible": False, "motivo": "no se encontró el droplet"}
            droplet_id = objetivo["id"]
            d = objetivo
        else:
            r = httpx.get(f"{API}/droplets/{droplet_id}", headers=_headers(tok), timeout=TIMEOUT)
            if r.status_code != 200:
                return {"disponible": False, "motivo": f"HTTP {r.status_code}"}
            d = (r.json() or {}).get("droplet") or {}
    except httpx.HTTPError as exc:
        return {"disponible": False, "motivo": str(exc)[:200]}
    return {
        "disponible": True,
        "id": d.get("id"),
        "nombre": d.get("name"),
        "region": (d.get("region") or {}).get("slug"),
        "tamano": d.get("size_slug"),
        "vcpus": d.get("vcpus"),
        "ram_mb": d.get("memory"),
        "disco_gb": d.get("disk"),
        "ip_publica": next(
            (n.get("ip_address") for n in d.get("networks", {}).get("v4", []) if n.get("type") == "public"),
            None,
        ),
        "creado_en": d.get("created_at"),
    }
