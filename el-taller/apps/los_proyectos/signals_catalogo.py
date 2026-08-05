"""El proveedor que se le pone a un producto EN UN PROYECTO se liga al catálogo.

LC 2026-08-04 (Oscar): «el proveedor que se le pone a un proyecto los liga de
forma segura y fuerte en el backend. Si en un proyecto algo se asigna a otro
proveedor, se le liga también para ese proyecto pero el principal (primero) se
mantiene».

Traducción a mecanismo:

* La línea del proyecto (`ProyectoProducto.proveedor`) es la verdad de ESE
  proyecto y no se toca nunca desde aquí.
* Ese proveedor se agrega a `Servicio.proveedores` (la lista de quién puede
  surtir el producto), así que la próxima vez ya aparece marcado en la ficha del
  producto y en su filtro. Es el «ligado fuerte».
* `Servicio.proveedor_principal` **no se mueve**: sólo se ocupa si estaba vacío
  (catálogo recién sembrado o producto sin proveedor todavía). Por eso existe ese
  FK — el «primero» de la M2M era el primero *alfabético*, así que ligar un
  proveedor nuevo podía robarle el default al de siempre.

Va en una señal y no en la vista porque las líneas se guardan desde muchos
lados: el formset del detalle (autoguardado), el modal de alta, el duplicado, el
mini-Chalán y los ejecutores del Dictado. Es defensiva: si algo falla, la señal
se calla — ligar un proveedor al catálogo nunca debe tumbar el guardado de un
proyecto.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def vincular_proveedor_al_catalogo(sender, instance, **kwargs) -> None:
    """post_save de ProyectoProducto: liga su proveedor al producto del catálogo."""
    proveedor_id = getattr(instance, "proveedor_id", None)
    servicio = getattr(instance, "servicio", None)
    if not proveedor_id or servicio is None:
        return
    try:
        # `add` es idempotente: si ya estaba ligado, no hace nada.
        servicio.proveedores.add(proveedor_id)
        if servicio.proveedor_principal_id is None:
            servicio.proveedor_principal_id = proveedor_id
            servicio.save(update_fields=["proveedor_principal"])
    except Exception:  # pragma: no cover - defensivo
        logger.warning(
            "No se pudo ligar el proveedor %s al producto %s",
            proveedor_id, getattr(servicio, "pk", "?"), exc_info=True,
        )
