"""Servicios internos — último evento Portavoz emitido, items DLQ,
último backup local + remoto, último deploy.
"""

from __future__ import annotations

import os
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


# Dónde buscar los respaldos locales, en orden. La ruta estaba cableada a
# `/opt/el-despacho/backups`, que era la del droplet; con la mudanza el proyecto
# pasó a `/mnt/el-despacho` y el panel decía «no existe» sin que nada estuviera
# roto. Se prueban varias en vez de una porque el contenedor ve el disco del host
# bajo `/host` (lo monta `docker-compose.site.yml`) y el propio proyecto puede
# vivir en cualquier parte según la máquina.
_DONDE_BUSCAR_RESPALDOS = (
    "SITE_BACKUPS_DIR",  # si se declara, gana sobre todo lo demás
)
_RUTAS_RESPALDOS = (
    "/host/mnt/el-despacho/backups",
    "/host/opt/el-despacho/backups",
    "/mnt/el-despacho/backups",
    "/opt/el-despacho/backups",
    "/app/backups",
)


def _dir_respaldos(explicito: Path | None = None) -> Path | None:
    if explicito:
        return explicito if explicito.exists() else None
    for var in _DONDE_BUSCAR_RESPALDOS:
        v = os.environ.get(var)
        if v and Path(v).exists():
            return Path(v)
    for ruta in _RUTAS_RESPALDOS:
        if Path(ruta).exists():
            return Path(ruta)
    return None


def ultimo_backup_local(backups_dir: Path | None = None) -> dict[str, Any]:
    p = _dir_respaldos(backups_dir)
    if p is None:
        return {"disponible": False, "motivo": "no encontré la carpeta de respaldos"}
    archivos = sorted(p.glob("db-*.sql.gz"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not archivos:
        return {"disponible": False, "motivo": "sin backups"}
    a = archivos[0]
    return {
        "disponible": True,
        "archivo": a.name,
        "carpeta": str(p),
        "cuantos": len(archivos),
        "tamano_bytes": a.stat().st_size,
        "creado_en_ts": a.stat().st_mtime,
    }


def ultimo_backup_remoto(archivo: str | None = None) -> dict[str, Any]:
    """Último registro en `site_backup_remoto` (escrito por archivo.sh tras el
    rsync→HAL).

    `archivo` filtra por qué se respaldó. Hace falta porque `archivo.sh` registra
    DOS cosas por corrida —el dump de la base y los medios de El Almacén, con
    `archivo="medios"`— y sin filtrar, el panel enseñaba el que quedó último y
    daba a entender que el otro no existe. Son dos copias distintas y las dos
    importan: la base sin las fotos, o las fotos sin la base, no reconstruyen
    nada.
    """
    try:
        from apps.el_site.models import SiteBackupRemoto
        qs = SiteBackupRemoto.objects.order_by("-creado_en")
        if archivo == "medios":
            qs = qs.filter(archivo="medios")
        elif archivo == "base":
            qs = qs.exclude(archivo="medios")
        row = qs.first()
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
        "backup_remoto": ultimo_backup_remoto("base"),
        "backup_medios": ultimo_backup_remoto("medios"),
        "deploy": ultimo_deploy(),
    }
