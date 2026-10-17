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


def _rol_del_proceso(proceso) -> str:
    """Cómo se nombra a un proveedor que entra por un proceso del producto."""
    return "impresión" if proceso.tipo == proceso.TIPO_IMPRESION else "proceso"


def proveedores_de_la_linea(pp, procesos) -> list[dict]:
    """Todos los proveedores que tocan esta línea, con su rol y sin repetirse.

    LC 2026-10-14 (Oscar): «en los proveedores quiero que incluya los de
    impresión etc». La columna sólo decía el proveedor del producto; el de la
    impresión o el de otros procesos (bordado, ponchado…) no salía, y es justo
    a quien el taller tiene que mandarle el trabajo.

    Orden: primero el del producto, luego los de los procesos en el orden de la
    tarjeta. Si un mismo proveedor hace varias cosas se junta en UN renglón con
    todos sus roles («Bordados Mx · producto, impresión»), no aparece dos veces.
    """
    vistos: dict[int, dict] = {}

    def _sumar(proveedor, rol: str) -> None:
        if proveedor is None:
            return
        previo = vistos.get(proveedor.pk)
        if previo is None:
            vistos[proveedor.pk] = {"nombre": proveedor.razon_social, "roles": [rol]}
        elif rol not in previo["roles"]:
            previo["roles"].append(rol)

    _sumar(pp.proveedor, "producto")
    for pr in procesos:
        _sumar(pr.proveedor, _rol_del_proceso(pr))
    return list(vistos.values())


def _otros_proveedores(p, filas) -> list[dict]:
    """Los proveedores asignados al PROYECTO (no a un producto) que ninguna
    línea ya nombra: a quién más se le encargó algo."""
    en_filas = {x["nombre"] for f in filas for x in f["proveedores"]}
    otros = []
    for a in p.proveedores_asignados.select_related("proveedor").order_by("compromiso", "pk"):
        nombre = a.proveedor.razon_social
        if nombre in en_filas or any(o["nombre"] == nombre for o in otros):
            continue
        otros.append({"nombre": nombre, "tipo": a.get_tipo_display().lower()})
    return otros


def _ot_contexto(p, cfg) -> dict:
    filas = []
    con_proveedores = cfg.bloque("proveedores")
    for pp in _lineas(p, todas=True):
        if not pp.incluir_en_calculo:
            continue
        # Los procesos se leen también para el bloque de proveedores: el de la
        # impresión sale ahí aunque el bloque «Procesos» esté apagado.
        procesos = list(pp.procesos.select_related("proveedor").order_by("orden", "pk")) \
            if (cfg.bloque("procesos") or con_proveedores) else []
        filas.append({"pp": pp,
                      "procesos": procesos if cfg.bloque("procesos") else [],
                      "proveedores": proveedores_de_la_linea(pp, procesos) if con_proveedores else [],
                      "foto": _foto(pp) if cfg.bloque("fotos") else ""})
    responsables = []
    if cfg.bloque("responsables"):
        for a in p.asignaciones.select_related("usuario").order_by("pk"):
            nombre = (getattr(a.usuario, "nombre_completo", "") or "").strip() or a.usuario.email
            responsables.append(f"{nombre} ({a.get_rol_en_proyecto_display().lower()})")
    return {"p": p, "filas": filas, "responsables": responsables,
            "otros_proveedores": _otros_proveedores(p, filas) if con_proveedores else []}


ORDEN_TRABAJO = Documento(
    definicion=ORDEN_TRABAJO_DEF,
    plantilla="imprenta/documentos/orden_trabajo.html",
    rotulo="Orden de trabajo",
    obtener=_proyecto, puede=_puede, contexto=_ot_contexto,
    piezas=_piezas, ejemplos=_ejemplos,
    titulo=lambda p: f"Orden de trabajo · {p.nombre or p.codigo}",
    fecha=lambda p: date.today(),
)
