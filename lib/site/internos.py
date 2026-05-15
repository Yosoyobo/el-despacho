"""Servicios internos — último evento Portavoz emitido, items DLQ,
último backup local + remoto, último deploy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def ultimo_evento_portavoz() -> dict[str, Any]:
    """Inspecciona el head de la cola Redis del Portavoz sin consumirlo.
    No accede a un evento "histórico" porque la cola es FIFO — esto solo
    sirve para ver el siguiente pendiente. Si está vacía, retorna `disponible=False`.
    """
    try:
        import redis

        from . import redis_status
        c = redis.Redis.from_url(redis_status.REDIS_URL, socket_connect_timeout=2)
        cola = c.llen(redis_status.COLA_PORTAVOZ)
        if cola == 0:
            return {"disponible": False, "motivo": "cola vacía"}
        head = c.lindex(redis_status.COLA_PORTAVOZ, 0)
        if head is None:
            return {"disponible": False, "motivo": "head vacío"}
        import json
        d = json.loads(head)
        return {
            "disponible": True,
            "tipo": d.get("tipo"),
            "emitido_en": d.get("emitido_en"),
            "actor_email": d.get("actor_email"),
            "items_pendientes": cola,
        }
    except Exception as exc:  # noqa: BLE001
        return {"disponible": False, "motivo": str(exc)[:120]}


def items_dlq() -> int:
    try:
        import redis

        from . import redis_status
        c = redis.Redis.from_url(redis_status.REDIS_URL, socket_connect_timeout=2)
        return int(c.llen(redis_status.COLA_FALLIDOS) or 0)
    except Exception:
        return 0


def ultimo_backup_local(backups_dir: Path | None = None) -> dict[str, Any]:
    p = backups_dir or Path("/opt/el-despacho/backups")
    if not p.exists():
        return {"disponible": False, "motivo": f"{p} no existe"}
    archivos = sorted(p.glob("db-*.sql.gz"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not archivos:
        return {"disponible": False, "motivo": "sin backups"}
    a = archivos[0]
    return {
        "disponible": True,
        "archivo": a.name,
        "tamano_bytes": a.stat().st_size,
        "creado_en_ts": a.stat().st_mtime,
    }


def ultimo_backup_remoto() -> dict[str, Any]:
    """Último registro en `site_backup_remoto` (escrito por archivo.sh
    cuando rsync→HAL es exitoso)."""
    try:
        from apps.el_site.models import SiteBackupRemoto
        row = SiteBackupRemoto.objects.order_by("-creado_en").first()
    except Exception as exc:  # noqa: BLE001
        return {"disponible": False, "motivo": str(exc)[:120]}
    if not row:
        return {"disponible": False, "motivo": "sin registros"}
    return {
        "disponible": True,
        "archivo": row.archivo,
        "destino": row.destino,
        "estado": row.estado,
        "tamano_bytes": row.tamano_bytes,
        "creado_en": row.creado_en.isoformat(),
    }


def ultimo_deploy() -> dict[str, Any]:
    try:
        from apps.el_site.models import SiteDeploy
        row = SiteDeploy.objects.order_by("-creado_en").first()
    except Exception as exc:  # noqa: BLE001
        return {"disponible": False, "motivo": str(exc)[:120]}
    if not row:
        return {"disponible": False, "motivo": "sin registros"}
    return {
        "disponible": True,
        "estado": row.estado,
        "commit": row.commit,
        "creado_en": row.creado_en.isoformat(),
    }


def snapshot() -> dict[str, Any]:
    return {
        "portavoz_head": ultimo_evento_portavoz(),
        "portavoz_dlq": items_dlq(),
        "backup_local": ultimo_backup_local(),
        "backup_remoto": ultimo_backup_remoto(),
        "deploy": ultimo_deploy(),
    }
