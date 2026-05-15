"""Batería de chequeos de integraciones externas e internas del Droplet.

Cada función retorna un dict con al menos `estado` ("ok"|"error"|"no_configurada")
y `latencia_ms`. `mensaje_error` aparece si estado != ok.

Las llamadas a Anthropic/OpenAI cobran tokens (mínimos: max_tokens=1). El cron
diario las ejecuta una vez al día — 365 llamadas/año por provider, < 1 ¢.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any

import httpx

TIMEOUT = 8.0


def _credencial(clave: str) -> str | None:
    try:
        from ajustes.models.credencial import Credencial
        return Credencial.obtener(clave)
    except Exception:
        return None


# ── Anthropic ────────────────────────────────────────────────────────────────

def chequear_anthropic() -> dict[str, Any]:
    key = _credencial("anthropic_api_key")
    if not key:
        return {"estado": "no_configurada", "mensaje_error": "anthropic_api_key no configurada"}
    t0 = time.monotonic()
    try:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ok"}],
            },
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        return {"estado": "error", "mensaje_error": str(exc)[:200], "latencia_ms": int((time.monotonic() - t0) * 1000)}
    latencia = int((time.monotonic() - t0) * 1000)
    if r.status_code != 200:
        return {"estado": "error", "mensaje_error": f"HTTP {r.status_code}: {r.text[:120]}", "latencia_ms": latencia}
    return {"estado": "ok", "latencia_ms": latencia}


# ── OpenAI ───────────────────────────────────────────────────────────────────

def chequear_openai() -> dict[str, Any]:
    key = _credencial("openai_api_key")
    if not key:
        return {"estado": "no_configurada", "mensaje_error": "openai_api_key no configurada"}
    t0 = time.monotonic()
    try:
        r = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ok"}],
            },
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        return {"estado": "error", "mensaje_error": str(exc)[:200], "latencia_ms": int((time.monotonic() - t0) * 1000)}
    latencia = int((time.monotonic() - t0) * 1000)
    if r.status_code != 200:
        return {"estado": "error", "mensaje_error": f"HTTP {r.status_code}: {r.text[:120]}", "latencia_ms": latencia}
    return {"estado": "ok", "latencia_ms": latencia}


# ── Docker socket ────────────────────────────────────────────────────────────

def chequear_docker() -> dict[str, Any]:
    from . import contenedores
    if not contenedores.disponible():
        return {"estado": "no_configurada", "mensaje_error": "docker.sock no montado"}
    t0 = time.monotonic()
    info = contenedores.info()
    latencia = int((time.monotonic() - t0) * 1000)
    if not info.get("disponible"):
        return {"estado": "error", "mensaje_error": info.get("error", "docker info falló"), "latencia_ms": latencia}
    return {"estado": "ok", "latencia_ms": latencia}


# ── Tailscale ────────────────────────────────────────────────────────────────

def chequear_tailscale() -> dict[str, Any]:
    """Corre `tailscale status --json` si el binario está disponible (en el
    host, no en el container). Si no hay binario, retorna no_configurada."""
    binario = shutil.which("tailscale") or "/usr/bin/tailscale"
    if not os.path.exists(binario):
        return {"estado": "no_configurada", "mensaje_error": "binario tailscale no presente"}
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [binario, "status", "--json"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"estado": "error", "mensaje_error": str(exc)[:200], "latencia_ms": int((time.monotonic() - t0) * 1000)}
    latencia = int((time.monotonic() - t0) * 1000)
    if proc.returncode != 0:
        return {"estado": "error", "mensaje_error": (proc.stderr or "rc!=0")[:200], "latencia_ms": latencia}
    return {"estado": "ok", "latencia_ms": latencia}


# ── n8n vía Tailscale ────────────────────────────────────────────────────────

def chequear_n8n() -> dict[str, Any]:
    url = _credencial("n8n_health_url")
    if not url:
        return {"estado": "no_configurada", "mensaje_error": "n8n_health_url no configurada"}
    t0 = time.monotonic()
    try:
        r = httpx.get(url, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        return {"estado": "error", "mensaje_error": str(exc)[:200], "latencia_ms": int((time.monotonic() - t0) * 1000)}
    latencia = int((time.monotonic() - t0) * 1000)
    if r.status_code >= 400:
        return {"estado": "error", "mensaje_error": f"HTTP {r.status_code}", "latencia_ms": latencia}
    return {"estado": "ok", "latencia_ms": latencia}
