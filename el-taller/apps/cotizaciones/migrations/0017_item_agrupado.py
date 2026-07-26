"""Líneas agrupadas: procesos de VENTA dentro del bloque de su producto.

LC 2026-07-26 (Oscar). Aditiva: `agrupado` nace en False, así que todas las
líneas existentes siguen imprimiéndose como su propio bloque numerado.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0016_item_imagen"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacionitem",
            name="agrupado",
            field=models.BooleanField(
                default=False,
                help_text="Se imprime dentro del bloque del concepto anterior (proceso de venta).",
            ),
        ),
    ]
