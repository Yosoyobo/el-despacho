"""LC 2026-08-04 (Oscar) — puebla la Descripción de cada línea de producto con la
especificación que YA se escribió en sus cotizaciones, y borra las notas viejas.

Contexto: en `0028` el campo `nota` de `ProyectoProducto` pasó a ser la
**Descripción** del elemento — la especificación que el cliente lee en el
documento. Oscar: «necesitamos sustituir lo que ya se escribió en especificaciones
de varias cotizaciones y eso es el nuevo campo de notas; las notas anteriores por
producto se pueden eliminar».

Así que:

1. **Se borra** lo que hubiera en `nota` (eran notas internas — no sirven como
   especificación y no deben llegar al cliente).
2. **Se copia** el texto de la especificación desde el `CotizacionItem` que le
   corresponde, tomando **la versión más reciente que tenga algo escrito** (es lo
   último que alguien redactó a mano).

El texto se copia **verbatim**, incluido su primer renglón de piezas: `esqueleto`
detecta que ya arranca con «N pz» y le refresca el conteo en vez de anteponer otro
(conservando cosas como «(3 colores, 35 pz c/u)»).

Emparejado igual que `descripcion.indice_previo`: primero por
`(servicio, variacion)` y, de respaldo, por el nombre del concepto — así una línea
a la que le cambiaron el producto no se queda sin su texto.

**No es reversible en su contenido**: al revertir se vacían las descripciones (las
notas internas originales se descartaron a propósito, no hay de dónde recuperarlas).
"""

from __future__ import annotations

from django.db import migrations


def _indice_por_proyecto(Cotizacion):
    """`{proyecto_id: {llave: texto}}` con la especificación más reciente escrita.

    Se recorren las versiones de **menor a mayor** y se sobreescribe, así queda el
    texto de la versión más nueva que tenga contenido para esa llave.
    """
    indices: dict[int, dict] = {}
    cots = (
        Cotizacion.objects.filter(version__gt=0, proyecto__isnull=False)
        .order_by("proyecto_id", "version")
        .prefetch_related("items")
    )
    # `iterator()` tras `prefetch_related` exige `chunk_size` (Django lo valida).
    for cot in cots.iterator(chunk_size=200):
        indice = indices.setdefault(cot.proyecto_id, {})
        for it in cot.items.all():
            texto = (it.descripcion or "").strip()
            if not texto:
                continue
            indice[("srv", it.servicio_id, it.variacion_id)] = texto
            nombre = (it.concepto or "").strip().lower()
            if nombre:
                indice[("nom", nombre)] = texto
    return indices


def poblar(apps, schema_editor):
    ProyectoProducto = apps.get_model("proyectos", "ProyectoProducto")
    Cotizacion = apps.get_model("cotizaciones", "Cotizacion")

    indices = _indice_por_proyecto(Cotizacion)
    pendientes = []
    lineas = ProyectoProducto.objects.select_related("servicio").iterator()
    for pp in lineas:
        indice = indices.get(pp.proyecto_id) or {}
        texto = indice.get(("srv", pp.servicio_id, pp.variacion_id))
        if not texto:
            # Respaldo por nombre: el alias del proyecto o el del catálogo.
            for candidato in (
                (pp.nombre_proyecto or "").strip().lower(),
                (pp.servicio.nombre if pp.servicio_id else "").strip().lower(),
            ):
                if candidato and indice.get(("nom", candidato)):
                    texto = indice[("nom", candidato)]
                    break
        # Sin especificación previa, la nota interna se va igual (decisión Oscar).
        nuevo = texto or ""
        if (pp.nota or "") != nuevo:
            pp.nota = nuevo
            pendientes.append(pp)
        if len(pendientes) >= 500:
            ProyectoProducto.objects.bulk_update(pendientes, ["nota"])
            pendientes.clear()
    if pendientes:
        ProyectoProducto.objects.bulk_update(pendientes, ["nota"])


def vaciar(apps, schema_editor):
    ProyectoProducto = apps.get_model("proyectos", "ProyectoProducto")
    ProyectoProducto.objects.exclude(nota="").update(nota="")


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0028_producto_descripcion"),
        # Se lee `CotizacionItem.concepto`/`descripcion`, así que la tabla debe
        # estar en su forma actual.
        ("cotizaciones", "0017_item_agrupado"),
    ]

    operations = [
        migrations.RunPython(poblar, vaciar),
    ]
