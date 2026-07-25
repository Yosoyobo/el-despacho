"""LC 2026-07 — el concepto (nombre) se separa de las especificaciones.

Hasta ahora `CotizacionItem.descripcion` guardaba solo el nombre del producto.
El documento nuevo necesita las dos cosas por separado: el nombre como título
numerado y un bloque multilínea con las especificaciones que lee el cliente
(piezas, material, color, branding).

**No migra datos a propósito.** Las líneas existentes se quedan con su nombre
dentro de `descripcion` y las properties `concepto_visible` / `detalle_lineas`
las leen bien; partir ese texto a ciegas podría romper las descripciones que
alguien escribió a mano.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0012_toggles_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacionitem",
            name="concepto",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
