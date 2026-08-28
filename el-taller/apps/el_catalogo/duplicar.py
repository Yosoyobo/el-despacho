"""Duplicar un producto del catálogo (LC 2026-08-28).

Oscar: «Duplicar producto tiene que existir. Y llevarse absolutamente todos los
datos.» Se copia TODO lo que define al producto:

    nombre (con «(copia)»), categoría, descripción, precio, costo, unidad,
    disponibilidad, la foto, los proveedores que lo surten, cuál es el
    principal, la impresión y los gastos de producción, y la calculadora de
    insumos. También sus variaciones.

Lo que NO viaja, y por qué:

- **El historial de usos** (`en_proyectos`, cotizaciones, facturas): es lo que
  le pasó al producto original, no un dato suyo. El duplicado nace sin historia.
- **Las marcas de captura** (quién y cuándo lo creó): las pone el duplicado.

La FOTO se copia por referencia al mismo archivo, no se sube otra vez — igual
que al duplicar un proyecto. Quitarla de uno de los dos sólo desliga: el archivo
nunca se borra del almacén.
"""

from __future__ import annotations

from django.db import transaction

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Servicio
from .models.variacion import Variacion

SUFIJO = " (copia)"
LARGO_NOMBRE = Servicio._meta.get_field("nombre").max_length


def nombre_para_copia(nombre: str) -> str:
    """«Playera» → «Playera (copia)», recortado al largo del campo."""
    base = (nombre or "").strip() or "Producto"
    if len(base) + len(SUFIJO) > LARGO_NOMBRE:
        base = base[: LARGO_NOMBRE - len(SUFIJO)].rstrip()
    return base + SUFIJO


@transaction.atomic
def duplicar_servicio(origen: Servicio, *, actor=None) -> Servicio:
    """Crea y devuelve la copia del producto."""
    copia = Servicio.objects.create(
        nombre=nombre_para_copia(origen.nombre),
        descripcion_default=origen.descripcion_default,
        unidad=origen.unidad,
        precio_base=origen.precio_base,
        costo=origen.costo,
        categoria=origen.categoria,
        activo=origen.activo,
        # La foto es una referencia al archivo del almacén; se comparte.
        imagen_file_id=origen.imagen_file_id,
        imagen_url=origen.imagen_url,
        proveedor_principal=origen.proveedor_principal,
        detalles_costo=dict(origen.detalles_costo or {}),
        procesos_default=list(origen.procesos_default or []),
        creado_por=actor if getattr(actor, "is_authenticated", False) else None,
    )
    copia.proveedores.set(origen.proveedores.all())
    for v in origen.variaciones.all():
        Variacion.objects.create(
            servicio=copia,
            nombre=v.nombre,
            costo=v.costo,
            impresion_activa=v.impresion_activa,
            impresion_costo=v.impresion_costo,
            impresion_descripcion=v.impresion_descripcion,
            descripcion=v.descripcion,
            disponible=v.disponible,
        )
    emitir(EventoPortavoz(
        tipo="catalogo.servicio_duplicado",
        actor_id=getattr(actor, "pk", None),
        actor_email=getattr(actor, "email", "") or "",
        payload={"origen_id": origen.pk, "servicio_id": copia.pk, "nombre": copia.nombre},
    ))
    return copia
