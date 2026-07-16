"""Ejecutores de la Ola 1 CUI (S-Chalan-MCP-V1 commit 4).

Rellena huecos de "lo que se hace con clicks pero aún no por conversación":
duplicar/archivar proyecto, quitar producto, archivar cliente/tarea, cambiar
estado de mandado, duplicar cotización y generar la factura del anticipo.

Mismo contrato que `basicos.py`/`avanzados.py`: `(accion, usuario, contexto)`,
lanza `ValueError` si el payload es inválido, la entidad no existe o el usuario
no tiene permiso (defensa en profundidad — el gating del catálogo ya filtra el
prompt, aquí se re-chequea antes de tocar la DB). Nada se aplica sin la
confirmación humana que garantiza `services.aplicar`. `archivar_*` es soft-delete
REVERSIBLE (`restaurar: true` lo revierte); el borrado permanente sigue vetado.
"""

from __future__ import annotations

import contextlib

from . import _gate, registrar
from .avanzados import _cotizacion_por_codigo, _exigir
from .basicos import _limpiar_slug, _resolver_cliente, _resolver_proyecto


def _resolver_tarea(tid, contexto=None):
    """Tarea por id numérico o `@accion_N` (entidad creada en el mismo dictado)."""
    from apps.el_pizarron.models.tarea import Tarea

    pk = None
    texto = str(tid or "").strip()
    if texto.startswith("@accion_"):
        idx = texto.replace("@accion_", "")
        creadas = (contexto or {}).get("entidades_creadas") or {}
        entidad = creadas.get(idx) or (creadas.get(int(idx)) if idx.isdigit() else None)
        if entidad:
            pk = entidad.get("id")
    if pk is None:
        with contextlib.suppress(TypeError, ValueError):
            pk = int(texto)
    tarea = Tarea.objects.filter(pk=pk).first() if pk else None
    _exigir(tarea is not None, f"Tarea `{tid}` no encontrada.")
    return tarea


# ── Proyectos ──────────────────────────────────────────────────────────────────

@registrar("duplicar_proyecto")
def duplicar_proyecto(accion, usuario, contexto=None):
    """Payload: proyecto_slug, nombre? (del duplicado)."""
    _gate(usuario, "es_admin", "duplicar proyectos")
    from apps.los_proyectos.services_duplicar import duplicar_proyecto as svc

    payload = accion.payload or {}
    origen = _resolver_proyecto(payload.get("proyecto_slug"), contexto)
    nombre = (payload.get("nombre") or f"{origen.nombre} (copia)").strip()
    nuevo = svc(origen, nombre=nombre[:200], actor=usuario)
    accion.entidad_tipo = "proyecto"
    accion.entidad_id = nuevo.pk


@registrar("quitar_producto_proyecto")
def quitar_producto_proyecto(accion, usuario, contexto=None):
    """Payload: proyecto_slug, producto (nombre del servicio) | producto_id (pk de la línea)."""
    from apps.los_proyectos.models import ProyectoProducto

    from lib.permisos import puede_editar_proyecto
    payload = accion.payload or {}
    proyecto = _resolver_proyecto(payload.get("proyecto_slug"), contexto)
    _exigir(puede_editar_proyecto(usuario, proyecto), "No tienes permiso para editar este proyecto.")
    qs = ProyectoProducto.objects.filter(proyecto=proyecto)
    producto_id = payload.get("producto_id")
    if producto_id:
        with contextlib.suppress(TypeError, ValueError):
            qs = qs.filter(pk=int(producto_id))
    else:
        nombre = _limpiar_slug(str(payload.get("producto") or "").strip())
        _exigir(bool(nombre), "Indica `producto` (nombre) o `producto_id`.")
        qs = qs.filter(servicio__nombre__icontains=nombre)
    lineas = list(qs)
    _exigir(len(lineas) >= 1, "No encontré ese producto en el proyecto.")
    _exigir(len(lineas) == 1, "Varias líneas coinciden; especifica `producto_id`.")
    lineas[0].delete()
    with contextlib.suppress(Exception):
        proyecto.recalcular_monto_estimado()
    accion.entidad_tipo = "proyecto"
    accion.entidad_id = proyecto.pk


@registrar("archivar_proyecto")
def archivar_proyecto(accion, usuario, contexto=None):
    """Payload: proyecto_slug, restaurar? (bool → desarchiva). Reversible; no borra."""
    from lib.fecha import ahora_mx
    from lib.permisos import puede_editar_proyecto
    payload = accion.payload or {}
    proyecto = _resolver_proyecto(payload.get("proyecto_slug"), contexto)
    _exigir(puede_editar_proyecto(usuario, proyecto), "No tienes permiso para editar este proyecto.")
    restaurar = bool(payload.get("restaurar"))
    proyecto.archivado = not restaurar
    proyecto.archivado_en = None if restaurar else ahora_mx()
    proyecto.archivado_por = None if restaurar else usuario
    proyecto.save(update_fields=["archivado", "archivado_en", "archivado_por"])
    accion.entidad_tipo = "proyecto"
    accion.entidad_id = proyecto.pk


# ── Clientes ────────────────────────────────────────────────────────────────────

@registrar("archivar_cliente")
def archivar_cliente(accion, usuario, contexto=None):
    """Payload: cliente_slug, restaurar? (bool → reactiva). Reversible; no borra."""
    _gate(usuario, "puede_editar_cartera", "archivar clientes")
    payload = accion.payload or {}
    cliente = _resolver_cliente((payload.get("cliente_slug") or "").lower(), contexto)
    cliente.activo = bool(payload.get("restaurar"))  # archivar → activo=False; restaurar → True
    cliente.save(update_fields=["activo"])
    accion.entidad_tipo = "cliente"
    accion.entidad_id = cliente.pk


# ── Tareas / Mandados ────────────────────────────────────────────────────────────

@registrar("archivar_tarea")
def archivar_tarea(accion, usuario, contexto=None):
    """Payload: tarea_id (acepta @accion_N), restaurar? (bool). Reversible; no borra."""
    from lib.permisos import puede_ver_tarea
    payload = accion.payload or {}
    tarea = _resolver_tarea(payload.get("tarea_id"), contexto)
    _exigir(puede_ver_tarea(usuario, tarea), "No tienes acceso a esa tarea.")
    tarea.archivada = not bool(payload.get("restaurar"))
    tarea.save(update_fields=["archivada"])
    accion.entidad_tipo = "tarea"
    accion.entidad_id = tarea.pk


@registrar("cambiar_estado_mandado")
def cambiar_estado_mandado(accion, usuario, contexto=None):
    """Payload: tarea_id (el mandado cuelga de una tarea entrega/recoger),
    estado (en_camino|entregado|cancelado), motivo? (al cancelar)."""
    from apps.el_pizarron.mandados import cancelar, marcar_en_camino, marcar_entregado
    from apps.el_pizarron.models import Mandado

    from lib.permisos import puede_ver_tarea
    payload = accion.payload or {}
    tarea = _resolver_tarea(payload.get("tarea_id"), contexto)
    _exigir(puede_ver_tarea(usuario, tarea), "No tienes acceso a esa tarea/mandado.")
    mandado = Mandado.objects.filter(tarea=tarea).first()
    _exigir(mandado is not None, "Esa tarea no tiene un mandado (¿es de tipo entrega/recolección?).")
    estado = (payload.get("estado") or "").strip().lower()
    if estado == "en_camino":
        marcar_en_camino(mandado)
    elif estado == "entregado":
        marcar_entregado(mandado)
    elif estado == "cancelado":
        cancelar(mandado, motivo=(payload.get("motivo") or ""))
    else:
        raise ValueError("`estado` debe ser en_camino, entregado o cancelado.")
    accion.entidad_tipo = "tarea"
    accion.entidad_id = tarea.pk


# ── Cotizaciones / Facturación ────────────────────────────────────────────────────

@registrar("duplicar_cotizacion")
def duplicar_cotizacion(accion, usuario, contexto=None):
    """Payload: codigo."""
    _gate(usuario, "puede_crear_cotizaciones", "duplicar cotizaciones")
    from apps.cotizaciones.services import duplicar

    cot = _cotizacion_por_codigo((accion.payload or {}).get("codigo"))
    nueva = duplicar(cot, usuario)
    accion.entidad_tipo = "cotizacion"
    accion.entidad_id = nueva.pk


@registrar("generar_factura_anticipo")
def generar_factura_anticipo(accion, usuario, contexto=None):
    """Payload: codigo (cotización aprobada con anticipo configurado)."""
    _gate(usuario, "puede_crear_facturacion", "generar la factura del anticipo")
    from apps.cotizaciones.services import crear_factura_anticipo

    cot = _cotizacion_por_codigo((accion.payload or {}).get("codigo"))
    fac = crear_factura_anticipo(cot, usuario)
    accion.entidad_tipo = "factura"
    accion.entidad_id = fac.pk
