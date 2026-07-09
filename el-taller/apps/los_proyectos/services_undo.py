"""Undo de proyecto — pila de snapshots en Redis (Render-V2).

Decisión (sesión 2026-06-07): el historial de "deshacer" vive en Redis, no en
Postgres. Razón: el autoguardado dispara cada ~700ms tras dejar de teclear;
persistir un snapshot en Postgres por cada autoguardado sería caro. Redis ya
está en el stack y un `LPUSH`/`LTRIM` en memoria es órdenes de magnitud más
barato. El historial es una conveniencia transitoria (no dato durable): si
Redis reinicia, se pierde y no pasa nada.

- Clave por proyecto: lista `despacho:proyecto:undo:<pk>` (máx 5 frames).
- Coalescido: solo se empuja un frame nuevo si el último tiene más de
  `VENTANA_COALESCE` segundos. Así una ráfaga de tecleo = 1 paso deshacible,
  bajando escrituras y haciendo el Undo predecible.
- Cada frame es el estado del proyecto ANTES del guardado (para poder
  restaurarlo).

Si Redis está caído, todas las funciones degradan a no-op / 0 — el undo es
opcional, nunca debe tumbar el autoguardado.
"""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal

import redis
from django.db import transaction
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

MAX_FRAMES = 5
VENTANA_COALESCE = 15  # segundos
TTL = 60 * 60 * 24  # 1 día

_redis_client: redis.Redis | None = None


def _client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
    return _redis_client


def _clave(pk: int) -> str:
    return f"despacho:proyecto:undo:{pk}"


def _clave_ts(pk: int) -> str:
    return f"despacho:proyecto:undo_ts:{pk}"


# ── Serialización ──────────────────────────────────────────────────────────

def _iso(dt):
    return dt.isoformat() if dt else None


def snapshot_estado(proyecto) -> dict:
    """Captura el estado restaurable del proyecto: campos escalares + productos
    (con sus procesos) + equipo asignado."""
    productos = []
    for pp in proyecto.productos.prefetch_related("procesos").all():
        productos.append({
            "servicio_id": pp.servicio_id,
            "variacion_id": pp.variacion_id,
            "proveedor_id": pp.proveedor_id,
            "cantidad": pp.cantidad,
            "precio_unitario": str(pp.precio_unitario) if pp.precio_unitario is not None else None,
            "costo_unitario": str(pp.costo_unitario) if pp.costo_unitario is not None else None,
            "merma": pp.merma,
            "incluir_en_calculo": pp.incluir_en_calculo,
            "nota": pp.nota,
            "procesos": [
                {
                    "tipo": pr.tipo,
                    "orden": pr.orden,
                    "proveedor_id": pr.proveedor_id,
                    "descripcion": pr.descripcion,
                    "costo": str(pr.costo or 0),
                }
                for pr in pp.procesos.all()
            ],
        })
    equipo = [
        {"usuario_id": a.usuario_id, "rol_en_proyecto": a.rol_en_proyecto}
        for a in proyecto.asignaciones.all()
    ]
    return {
        "proyecto": {
            "nombre": proyecto.nombre,
            "cliente_id": proyecto.cliente_id,
            "descripcion": proyecto.descripcion,
            "estado": proyecto.estado,
            "fecha_inicio": _iso(proyecto.fecha_inicio),
            "fecha_compromiso": _iso(proyecto.fecha_compromiso),
            "iva_exento": proyecto.iva_exento,
            "regimen_fiscal": proyecto.regimen_fiscal,
        },
        "productos": productos,
        "equipo": equipo,
    }


# ── Pila (push coalescido / count / pop) ─────────────────────────────────────

def registrar_frame(proyecto, *, ahora_ts: float) -> None:
    """Empuja el estado actual como un frame deshacible, salvo que el último
    frame se haya empujado hace menos de VENTANA_COALESCE segundos (coalesce)."""
    try:
        r = _client()
        clave_ts = _clave_ts(proyecto.pk)
        ultimo = r.get(clave_ts)
        if ultimo is not None and (ahora_ts - float(ultimo)) < VENTANA_COALESCE:
            return  # dentro de la ráfaga — no agregamos un paso nuevo
        frame = json.dumps(snapshot_estado(proyecto))
        clave = _clave(proyecto.pk)
        pipe = r.pipeline()
        pipe.lpush(clave, frame)
        pipe.ltrim(clave, 0, MAX_FRAMES - 1)
        pipe.expire(clave, TTL)
        pipe.set(clave_ts, ahora_ts, ex=TTL)
        pipe.execute()
    except (RedisError, OSError, ValueError):
        logger.warning("undo: no se pudo registrar frame del proyecto %s", proyecto.pk, exc_info=True)


def pasos_disponibles(proyecto) -> int:
    try:
        return int(_client().llen(_clave(proyecto.pk)))
    except (RedisError, OSError):
        return 0


def deshacer(proyecto) -> bool:
    """Restaura el frame más reciente y lo descarta. Devuelve True si restauró."""
    try:
        r = _client()
        frame = r.lpop(_clave(proyecto.pk))
        # Al deshacer, la siguiente edición debe poder crear un frame nuevo.
        r.delete(_clave_ts(proyecto.pk))
    except (RedisError, OSError):
        return False
    if not frame:
        return False
    try:
        datos = json.loads(frame)
    except (ValueError, TypeError):
        return False
    _restaurar(proyecto, datos)
    return True


def _restaurar(proyecto, datos: dict) -> None:
    """Aplica un snapshot al proyecto en una transacción: campos escalares,
    productos (recreados) y equipo (recreado)."""
    from .models import ProyectoAsignacion, ProyectoProducto
    from .models.proceso import ProyectoProductoProceso

    p = datos.get("proyecto", {})
    with transaction.atomic():
        proyecto.nombre = p.get("nombre", proyecto.nombre)
        proyecto.cliente_id = p.get("cliente_id", proyecto.cliente_id)
        proyecto.descripcion = p.get("descripcion", proyecto.descripcion)
        proyecto.estado = p.get("estado", proyecto.estado)
        proyecto.fecha_inicio = _parse_dt(p.get("fecha_inicio"))
        proyecto.fecha_compromiso = _parse_dt(p.get("fecha_compromiso"))
        proyecto.iva_exento = p.get("iva_exento", proyecto.iva_exento)
        proyecto.regimen_fiscal = p.get("regimen_fiscal", proyecto.regimen_fiscal)
        proyecto.save()

        # Productos: borrar y recrear (los PKs cambian; para undo da igual).
        proyecto.productos.all().delete()
        for d in datos.get("productos", []):
            pp = ProyectoProducto.objects.create(
                proyecto=proyecto,
                servicio_id=d["servicio_id"],
                variacion_id=d.get("variacion_id"),
                proveedor_id=d.get("proveedor_id"),
                cantidad=d.get("cantidad", 1),
                precio_unitario=_dec(d.get("precio_unitario")),
                costo_unitario=_dec(d.get("costo_unitario")),
                merma=d.get("merma", 0),
                incluir_en_calculo=d.get("incluir_en_calculo", True),
                nota=d.get("nota", ""),
            )
            for pr in d.get("procesos", []):
                ProyectoProductoProceso.objects.create(
                    producto=pp,
                    tipo=pr.get("tipo", "operativo"),
                    orden=pr.get("orden", 0),
                    proveedor_id=pr.get("proveedor_id"),
                    descripcion=pr.get("descripcion", ""),
                    costo=_dec(pr.get("costo")) or Decimal("0.00"),
                )

        # Equipo: borrar y recrear.
        proyecto.asignaciones.all().delete()
        for e in datos.get("equipo", []):
            ProyectoAsignacion.objects.create(
                proyecto=proyecto,
                usuario_id=e["usuario_id"],
                rol_en_proyecto=e.get("rol_en_proyecto", "disenador"),
            )
    proyecto.recalcular_monto_estimado()
    proyecto.refresh_from_db()


def _dec(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (ValueError, TypeError):
        return None


def _parse_dt(v):
    if not v:
        return None
    from django.utils.dateparse import parse_datetime
    return parse_datetime(v)
