"""S-Finanzas-UX (2026-07): TasaImpositiva.porcentaje a 4 decimales.

Permite tasas fraccionadas como la retención de IVA de honorarios (10.6667%).
Solo AlterField (max_digits 5→7, decimal_places 2→4); no toca datos.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ajustes", "0011_fiscal_honorarios"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tasaimpositiva",
            name="porcentaje",
            field=models.DecimalField(decimal_places=4, max_digits=7),
        ),
    ]
