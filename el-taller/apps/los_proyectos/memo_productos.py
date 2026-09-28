"""El memo de las líneas de producto de un proyecto.

`Proyecto._productos_calc()` alimenta TODO el dinero del proyecto (monto,
costo, IVA, retenciones, utilidad, margen, deuda por proveedor, gastos…) y cada
propiedad lo volvía a pedir. Medido (2026-08-24 y otra vez 2026-09-28), el
detalle de un proyecto con 8 líneas recargaba la lista **18 veces** por
petición: cinco consultas por recarga (líneas + procesos + su proveedor + ventas
+ escalas), o sea ~90 de sus 231 consultas.

El arreglo es el mismo patrón que el caché de permisos (`lib/permisos.py`,
S-Latencia-Ago24): la lista se memoiza en la PROPIA instancia de `Proyecto`, que
vive lo que dura la petición. No es un caché compartido entre peticiones ni
entre trabajadores, así que no le puede servir datos viejos a nadie más.

La única ventana en la que el memo podría mentir es dentro de UNA petición (o un
comando, o un test) que escribe líneas y vuelve a leer el dinero con la misma
instancia — el autoguardado del detalle hace exactamente eso. Por eso hay tres
seguros:

1. **Signals.** El `post_save`/`post_delete` de `ProyectoProducto`, sus procesos,
   ventas y escalas —y de `Servicio`/`Variacion`, de donde se heredan precio y
   costo— suben `_VERSION`, y un memo llenado con una versión anterior se
   descarta.
2. **Las escrituras que NO disparan signals.** `QuerySet.update()`,
   `bulk_update()` y `bulk_create()` se saltan los signals. Las cuatro tablas de
   las líneas usan `QuerySetDelDinero`, que invalida al terminar cualquiera de
   ellas — también desde un related manager (`pp.escalas.update(...)`), porque
   Django los arma a partir del manager del modelo. Así no depende de que cada
   sitio que escribe se acuerde de avisar.
3. **El camino que escribe dinero lee fresco.** `recalcular_monto_estimado` y
   `refresh_from_db` olvidan el memo antes de leer.

La versión es por proceso, no por proyecto: si otro hilo guarda una línea de
cualquier proyecto, todos los memos del proceso se descartan. Sobra lectura en
el peor caso, nunca falta. Lo que NO cubre es SQL crudo o una escritura desde
otro proceso a media petición — ninguno de los dos existe hoy, y el segundo ya
daba lecturas inconsistentes antes del memo (cada propiedad veía otra foto).
"""

from __future__ import annotations

import contextlib

from django.db import models

_VERSION = 0

# El memo vive en el `__dict__` de la instancia: `(version, [lineas])`.
ATRIBUTO = "_despacho_memo_productos"


def version() -> int:
    return _VERSION


def invalidar(*args, **kwargs) -> None:
    """Descarta todos los memos vigentes. Firma de receptor de signal, así se
    conecta directo."""
    global _VERSION
    _VERSION += 1


def olvidar(proyecto) -> None:
    """Olvida el memo de UNA instancia (el camino que escribe dinero)."""
    with contextlib.suppress(AttributeError):  # instancia sin __dict__ (raro)
        proyecto.__dict__.pop(ATRIBUTO, None)


class QuerySetDelDinero(models.QuerySet):
    """QuerySet de las tablas de las que sale el dinero de un proyecto: invalida
    los memos al escribir por los caminos que no disparan signals."""

    def update(self, **kwargs):
        filas = super().update(**kwargs)
        invalidar()
        return filas

    def bulk_update(self, objs, fields, batch_size=None):
        filas = super().bulk_update(objs, fields, batch_size=batch_size)
        invalidar()
        return filas

    def bulk_create(self, objs, *args, **kwargs):
        creados = super().bulk_create(objs, *args, **kwargs)
        invalidar()
        return creados


def conectar_signals() -> None:
    """Conecta la invalidación a todo lo que cambia el dinero de una línea.

    `weak=False` (fix V6): con el default la referencia se puede recolectar y la
    señal muere en silencio. Aquí el receptor es de módulo, pero el patrón del
    repo se mantiene para que nadie lo cambie sin pensarlo.
    """
    from apps.el_catalogo.models import Servicio, Variacion
    from apps.los_proyectos.models import (
        ProyectoProducto,
        ProyectoProductoEscala,
        ProyectoProductoProceso,
        ProyectoProductoVenta,
    )
    from django.db.models.signals import post_delete, post_save

    for modelo in (
        ProyectoProducto, ProyectoProductoProceso, ProyectoProductoVenta,
        ProyectoProductoEscala, Servicio, Variacion,
    ):
        etiqueta = f"{modelo._meta.app_label}.{modelo._meta.model_name}"
        post_save.connect(invalidar, sender=modelo, weak=False,
                          dispatch_uid=f"memo_productos_save_{etiqueta}")
        post_delete.connect(invalidar, sender=modelo, weak=False,
                            dispatch_uid=f"memo_productos_del_{etiqueta}")
