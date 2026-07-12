"""Ejecutores de creación de Catálogo — servicios, variaciones, proveedores.

Cierra el bug "El Chalán no sabe crear productos". El Catálogo se administra
manualmente desde su módulo; aquí habilitamos SOLO la CREACIÓN (no editar ni
borrar — `modificar_catalogo` sigue prohibido en `TIPOS_PROHIBIDOS`).

Mismo contrato que `basicos.py`/`avanzados.py`: `(accion, usuario, contexto)`,
lanza `ValueError` si el payload es inválido o el usuario no tiene permiso.
Re-chequea `catalogo.crear` (defensa en profundidad, regla de seguridad #2).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from . import _gate, registrar
from .basicos import _limpiar_slug, _ref_anterior


def _decimal(valor, clave: str, *, default="0") -> Decimal:
    try:
        d = Decimal(str(valor if valor not in (None, "") else default)).quantize(Decimal("0.01"))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError(f"`{clave}` inválido: {valor}") from exc
    if d < 0:
        raise ValueError(f"`{clave}` no puede ser negativo.")
    return d


def _resolver_categoria(nombre: str):
    """Categoría del Catálogo por nombre exacto o icontains. Las categorías las
    administra La Gerencia, así que NO se crean aquí — error útil si no existe."""
    from apps.el_catalogo.models import CategoriaServicio
    nombre = _limpiar_slug((nombre or "").strip())
    if not nombre:
        cat = CategoriaServicio.objects.filter(activa=True).order_by("orden").first()
        if cat:
            return cat
        raise ValueError("No hay categorías activas en el Catálogo.")
    cat = (
        CategoriaServicio.objects.filter(nombre__iexact=nombre, activa=True).first()
        or CategoriaServicio.objects.filter(nombre__icontains=nombre, activa=True).first()
    )
    if not cat:
        disponibles = ", ".join(
            CategoriaServicio.objects.filter(activa=True).values_list("nombre", flat=True)[:10]
        )
        raise ValueError(f"Categoría `{nombre}` no encontrada. Disponibles: {disponibles or '—'}.")
    return cat


def _resolver_servicio(clave: str, contexto=None):
    """Servicio por `@accion_N` (creado en el mismo dictado), nombre exacto o
    icontains."""
    from apps.el_catalogo.models import Servicio
    clave = _limpiar_slug((clave or "").strip())
    if not clave:
        raise ValueError("Falta el servicio al que pertenece la variación (`servicio`).")
    ref_id = _ref_anterior(clave, contexto, "servicio")
    if ref_id:
        srv = Servicio.objects.filter(pk=ref_id).first()
        if srv:
            return srv
    srv = (
        Servicio.objects.filter(nombre__iexact=clave, activo=True).first()
        or Servicio.objects.filter(nombre__icontains=clave, activo=True).first()
    )
    if not srv:
        raise ValueError(f"Servicio `{clave}` no encontrado en el Catálogo.")
    return srv


@registrar("crear_servicio")
def crear_servicio(accion, usuario, contexto=None):
    """Crea un servicio/producto del Catálogo.

    Payload: nombre, precio_base, categoria? (nombre), costo?, unidad?,
    descripcion?.
    """
    _gate(usuario, "puede_crear_catalogo", "crear productos del Catálogo")
    from apps.el_catalogo.models import Servicio

    payload = accion.payload or {}
    nombre = (payload.get("nombre") or "").strip()
    if not nombre:
        raise ValueError("Falta `nombre` del producto.")
    categoria = _resolver_categoria(payload.get("categoria") or payload.get("categoria_nombre"))

    srv = Servicio.objects.create(
        nombre=nombre[:150],
        categoria=categoria,
        precio_base=_decimal(payload.get("precio_base"), "precio_base"),
        costo=_decimal(payload.get("costo"), "costo"),
        unidad=(payload.get("unidad") or "pieza")[:30],
        descripcion_default=(payload.get("descripcion") or ""),
        creado_por=usuario,
    )
    accion.entidad_tipo = "servicio"
    accion.entidad_id = srv.pk
    _emitir("catalogo.servicio_creado", usuario, {"servicio_id": srv.pk, "nombre": srv.nombre})


@registrar("actualizar_servicio")
def actualizar_servicio(accion, usuario, contexto=None):
    """Edita un producto del Catálogo (LC #153). El Chalán solo edita productos
    ya existentes — modificar el catálogo requiere permiso `catalogo.editar`.

    Payload: servicio (nombre o @accion_N), y los campos a cambiar:
    nombre_nuevo?, precio_base?, costo?, unidad?, descripcion?, disponible?.
    """
    _gate(usuario, "puede_editar_catalogo", "editar productos del Catálogo")
    payload = accion.payload or {}
    srv = _resolver_servicio(payload.get("servicio") or payload.get("nombre") or "", contexto)
    cambios = []
    if payload.get("nombre_nuevo"):
        srv.nombre = str(payload["nombre_nuevo"])[:150]
        cambios.append("nombre")
    if payload.get("precio_base") not in (None, ""):
        srv.precio_base = _decimal(payload.get("precio_base"), "precio_base")
        cambios.append("precio_base")
    if payload.get("costo") not in (None, ""):
        srv.costo = _decimal(payload.get("costo"), "costo")
        cambios.append("costo")
    if payload.get("unidad"):
        srv.unidad = str(payload["unidad"])[:30]
        cambios.append("unidad")
    if "descripcion" in payload:
        srv.descripcion_default = str(payload.get("descripcion") or "")
        cambios.append("descripcion_default")
    if "disponible" in payload:
        srv.activo = bool(payload["disponible"])
        cambios.append("activo")
    if not cambios:
        raise ValueError("No indicaste qué cambiar del producto (precio, costo, nombre…).")
    srv.save(update_fields=[*cambios, "actualizado_en"])
    accion.entidad_tipo = "servicio"
    accion.entidad_id = srv.pk
    _emitir("catalogo.servicio_actualizado", usuario, {"servicio_id": srv.pk, "cambios": cambios})


@registrar("crear_variacion")
def crear_variacion(accion, usuario, contexto=None):
    """Crea una variación de un servicio existente.

    Payload: servicio (@accion_N o nombre), nombre, costo?, impresion_activa?,
    impresion_costo?, impresion_descripcion?, descripcion?.
    """
    _gate(usuario, "puede_crear_catalogo", "crear variaciones del Catálogo")
    from apps.el_catalogo.models import Variacion

    payload = accion.payload or {}
    servicio = _resolver_servicio(payload.get("servicio") or payload.get("servicio_slug"), contexto)
    nombre = (payload.get("nombre") or "").strip()
    if not nombre:
        raise ValueError("Falta `nombre` de la variación.")
    impresion = bool(payload.get("impresion_activa"))
    var = Variacion.objects.create(
        servicio=servicio,
        nombre=nombre[:150],
        costo=_decimal(payload.get("costo"), "costo"),
        impresion_activa=impresion,
        impresion_costo=_decimal(payload.get("impresion_costo"), "impresion_costo") if impresion else Decimal("0.00"),
        impresion_descripcion=(payload.get("impresion_descripcion") or "")[:250],
        descripcion=(payload.get("descripcion") or "")[:500],
    )
    accion.entidad_tipo = "variacion"
    accion.entidad_id = var.pk
    _emitir("catalogo.variacion_creada", usuario, {"variacion_id": var.pk, "servicio_id": servicio.pk})


@registrar("crear_proveedor")
def crear_proveedor(accion, usuario, contexto=None):
    """Crea un proveedor del Catálogo.

    Payload: razon_social, nombre_contacto?, email_contacto?, telefono?, rfc?,
    direccion?, notas?.
    """
    _gate(usuario, "puede_crear_catalogo", "crear proveedores del Catálogo")
    from apps.el_catalogo.models import Proveedor

    payload = accion.payload or {}
    razon = (payload.get("razon_social") or "").strip()
    if not razon:
        raise ValueError("Falta `razon_social` del proveedor.")
    direccion = (payload.get("direccion") or "")
    prov = Proveedor.objects.create(
        razon_social=razon[:200],
        nombre_contacto=(payload.get("nombre_contacto") or "")[:120],
        email_contacto=(payload.get("email_contacto") or "")[:254],
        telefono=(payload.get("telefono") or "")[:40],
        rfc=(payload.get("rfc") or "")[:20],
        direccion=direccion,
        direccion_fiscal=direccion,
        notas=(payload.get("notas") or ""),
        creado_por=usuario,
    )
    accion.entidad_tipo = "proveedor"
    accion.entidad_id = prov.pk
    _emitir("proveedor.creado", usuario, {"proveedor_id": prov.pk, "razon_social": prov.razon_social})


def _emitir(tipo: str, usuario, payload: dict) -> None:
    import contextlib
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo=tipo,  # type: ignore[arg-type]
            actor_id=getattr(usuario, "pk", None),
            actor_email=getattr(usuario, "email", None),
            payload=payload,
        ))
