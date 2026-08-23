"""Dirección desde la que salen los correos que manda El Chalán.

Sólo el ESQUEMA. El valor inicial lo pone la `0021`, separada a propósito:
ver CLAUDE.md §14 Bug I — una migración cambia el esquema o mueve datos, no
las dos cosas sobre la misma tabla.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ajustes", "0019_configuracion_rutas"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracioncorreo",
            name="remitente_chalan",
            field=models.EmailField(
                blank=True,
                default="",
                help_text=(
                    "Dirección desde la que salen los correos que manda El Chalán "
                    "cuando la plantilla no trae una propia. Vacío = el remitente general."
                ),
                max_length=254,
            ),
        ),
    ]
