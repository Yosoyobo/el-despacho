"""Documentos del proyecto: la remisión (al cliente) y la orden de trabajo (interna)."""

from __future__ import annotations

from datetime import date

from ..esquema import Bloque, Columna, DefinicionTipo
from .base import Documento


def _proyecto(pk):
    from apps.los_proyectos.models import Proyecto

    return Proyecto.objects.select_related("cliente").get(pk=pk)


def _puede(usuario, obj=None) -> bool:
    """Con el proyecto, quien lo puede ver; sin él (ejemplos), quien ve todos."""
    from lib import permisos

    if obj is None:
        return permisos.puede_ver_todos_proyectos(usuario)
    return permisos.puede_ver_proyecto(usuario, obj)


def _piezas(p) -> dict:
    return {"folio": p.codigo, "cliente": p.cliente.razon_social if p.cliente_id else "",
            "proyecto": p.nombre or p.codigo, "fecha": date.today().strftime("%Y-%m-%d"),
            "version": ""}


def _ejemplos(limite: int = 15):
    from apps.los_proyectos.models import Proyecto

    qs = (Proyecto.objects.filter(archivado=False).select_related("cliente")
          .order_by("-actualizado_en")[:limite])
    return [(p.pk, f"{p.codigo} · {p.cliente.razon_social} · {p.nombre}"[:90]) for p in qs]


def _foto(pp) -> str:
    from lib import almacen

    clave = pp.imagen_efectiva_file_id
    return almacen.url(clave, "w400", absoluta=True) if clave else ""


# ── Remisión / nota de entrega ──────────────────────────────────────────────

REMISION_DEF = DefinicionTipo(
    slug="remision",
    nombre="Remisión",
    subcarpeta="Remisiones",
    ayuda="Lo que se le entrega al cliente, con su firma de recibido.",
    bloques=(
        Bloque("fecha", "Fecha de entrega (arriba a la izquierda)"),
        Bloque("logo", "Logotipo"),
        Bloque("cliente", "Cliente y dirección de entrega"),
        Bloque("proyecto", "Proyecto"),
        Bloque("fotos", "Foto de cada producto", default=False),
        Bloque("precios", "Precios e importes", default=False,
               ayuda="Apagado, la remisión sólo dice qué y cuánto se entrega."),
        Bloque("notas", "La nota de cada producto", default=False),
    ),
    columnas=(
        Columna("cantidad", "Cant."),
        Columna("descripcion", "Descripción"),
        Columna("precio", "P. unitario"),
        Columna("importe", "Importe"),
        Columna("rotulo_entrega", "Entregar a"),
    ),
    firma_default=True,
    aceptacion_default=True,
    aceptacion_texto="Recibí de conformidad.",
    qr_opciones=("", "portal"),
)


def _lineas(p, *, todas: bool = False):
    qs = p.productos.select_related("servicio", "proveedor").order_by("orden", "pk")
    lineas = list(qs)
    if not todas:
        lineas = [pp for pp in lineas if pp.visible_pdf and pp.incluir_en_calculo]
    return lineas


def _remision_contexto(p, cfg) -> dict:
    from decimal import Decimal

    filas = []
    total = Decimal("0")
    for pp in _lineas(p):
        importe = (pp.precio_unitario or Decimal("0")) * pp.cantidad
        total += importe
        filas.append({"pp": pp, "importe": importe,
                      "foto": _foto(pp) if cfg.bloque("fotos") else ""})
    return {"p": p, "filas": filas, "total": total,
            "entrega": p.fecha_real_entrega or date.today(),
            "direccion": (p.cliente.direccion or "").strip() if p.cliente_id else ""}


REMISION = Documento(
    definicion=REMISION_DEF,
    plantilla="imprenta/documentos/remision.html",
    rotulo="Remisión",
    obtener=_proyecto, puede=_puede, contexto=_remision_contexto,
    piezas=_piezas, ejemplos=_ejemplos,
    titulo=lambda p: f"Remisión · {p.nombre or p.codigo}",
    fecha=lambda p: p.fecha_real_entrega or date.today(),
)


# ── Orden de trabajo (interna, para el taller y la maquila) ────────────────

ORDEN_TRABAJO_DEF = DefinicionTipo(
    slug="orden_trabajo",
    nombre="Orden de trabajo",
    subcarpeta="Órdenes de trabajo",
    ayuda="Para el taller: qué se produce, cuánto, con quién y para cuándo. No lleva precios de venta.",
    bloques=(
        Bloque("fecha", "Fecha (arriba a la izquierda)"),
        Bloque("logo", "Logotipo"),
        Bloque("cliente", "Cliente"),
        Bloque("compromiso", "Fecha de compromiso"),
        Bloque("responsables", "Responsables del proyecto"),
        Bloque("fotos", "Foto de cada producto"),
        Bloque("proveedores", "Proveedor de cada producto"),
        Bloque("procesos", "Procesos (impresión, bordado…)"),
        Bloque("merma", "Merma"),
        Bloque("costos", "Costos", default=False, ayuda="Lo que cuesta producir, no lo que se cobra."),
        Bloque("notas", "La nota de cada producto"),
        Bloque("descripcion", "La descripción del proyecto"),
    ),
    columnas=(
        Columna("producto", "Producto"),
        Columna("cantidad", "Cant."),
        Columna("merma", "Merma"),
        Columna("proveedor", "Proveedor"),
        Columna("costo", "Costo u."),
        Columna("rotulo_compromiso", "Entregar el"),
        Columna("rotulo_responsables", "Responsables"),
    ),
    aceptacion_texto="Recibí la orden de trabajo.",
    qr_opciones=("",),
)


def _ot_contexto(p, cfg) -> dict:
    filas = []
    for pp in _lineas(p, todas=True):
        if not pp.incluir_en_calculo:
            continue
        procesos = list(pp.procesos.select_related("proveedor").order_by("orden", "pk")) \
            if cfg.bloque("procesos") else []
        filas.append({"pp": pp, "procesos": procesos,
                      "foto": _foto(pp) if cfg.bloque("fotos") else ""})
    responsables = []
    if cfg.bloque("responsables"):
        for a in p.asignaciones.select_related("usuario").order_by("pk"):
            nombre = (getattr(a.usuario, "nombre_completo", "") or "").strip() or a.usuario.email
            responsables.append(f"{nombre} ({a.get_rol_en_proyecto_display().lower()})")
    return {"p": p, "filas": filas, "responsables": responsables}


ORDEN_TRABAJO = Documento(
    definicion=ORDEN_TRABAJO_DEF,
    plantilla="imprenta/documentos/orden_trabajo.html",
    rotulo="Orden de trabajo",
    obtener=_proyecto, puede=_puede, contexto=_ot_contexto,
    piezas=_piezas, ejemplos=_ejemplos,
    titulo=lambda p: f"Orden de trabajo · {p.nombre or p.codigo}",
    fecha=lambda p: date.today(),
)
