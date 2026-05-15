"""Postgres — chequeo SELECT 1 + tamaño total de la DB + conexiones activas.
Usa la conexión `default` de Django."""

from __future__ import annotations

import time
from typing import Any


def chequear() -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        return {"estado": "error", "mensaje_error": str(exc)[:200], "latencia_ms": int((time.monotonic() - t0) * 1000)}
    return {"estado": "ok", "latencia_ms": int((time.monotonic() - t0) * 1000)}


def detalles() -> dict[str, Any]:
    """Tamaño DB + conexiones activas. Si Postgres no responde, retorna
    `disponible=False`."""
    try:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database()), current_database()")
            tam, dbname = cur.fetchone()
            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
            (conexiones,) = cur.fetchone()
            cur.execute("SHOW server_version")
            (version,) = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        return {"disponible": False, "error": str(exc)[:200]}
    return {
        "disponible": True,
        "db": dbname,
        "tamano_mb": round(tam / (1024 * 1024), 2),
        "conexiones_activas": conexiones,
        "version": version,
    }
