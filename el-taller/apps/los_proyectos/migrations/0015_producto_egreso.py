"""FK ProyectoProducto.egreso → tesoreria.Egreso (marca de idempotencia).

Cuando un proyecto pasa a `en_proceso_produccion`, cada línea de producto
genera un Egreso; esta FK evita duplicar al re-disparar el signal. SET_NULL
para no perder la línea si el egreso se borra físicamente.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0014_estado_color_hex"),
        ("tesoreria", "0006_egreso_origen_proyecto"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyectoproducto",
            name="egreso",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lineas_proyecto",
                to="tesoreria.egreso",
            ),
        ),
    ]
