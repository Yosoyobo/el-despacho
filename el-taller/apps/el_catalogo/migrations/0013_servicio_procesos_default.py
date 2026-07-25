"""Impresión + procesos adicionales como plantilla del producto (LC 2026-07-25).

Aditiva: los productos existentes quedan con `[]` (sin procesos default), así
que nada cambia hasta que se capturen en la ficha del producto.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0012_servicio_detalles_costo"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicio",
            name="procesos_default",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
