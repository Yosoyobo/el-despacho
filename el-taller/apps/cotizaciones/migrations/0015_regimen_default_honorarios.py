"""Régimen fiscal por default = «IVA y Retenciones» (Oscar 2026-07-25).

Espejo de `los_proyectos.0025`. Solo el default; las cotizaciones existentes no
se tocan (además heredan el régimen del proyecto al generarse).
"""

from django.db import migrations, models

from lib.fiscal import REGIMENES_FISCALES


class Migration(migrations.Migration):
    dependencies = [("cotizaciones", "0014_titulo_documento_manual")]

    operations = [
        migrations.AlterField(
            model_name="cotizacion",
            name="regimen_fiscal",
            field=models.CharField(
                choices=REGIMENES_FISCALES, db_index=True,
                default="honorarios", max_length=12,
            ),
        ),
    ]
