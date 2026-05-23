"""S-LC-Feedback-V3: agrega campo `costo` a Servicio + a Variacion.

Permite calcular margen `(precio - costo) / precio` en la UI sin
necesidad de recapturar costo cada vez en proyectos y cotizaciones.

El default es 0 — los servicios existentes quedan con margen 100%
hasta que el admin capture su costo real.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0003_unidad"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicio",
            name="costo",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
