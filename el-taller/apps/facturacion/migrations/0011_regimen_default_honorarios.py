"""Régimen fiscal por default = «IVA y Retenciones» (Oscar 2026-07-25).

Espejo de `los_proyectos.0025`. El formulario ya lo ofrecía marcado por
default; lo que faltaba era el default del MODELO, que es el que usan el
ejecutor `crear_factura` de El Chalán y cualquier alta programática.
"""

from django.db import migrations, models

from lib.fiscal import REGIMENES_FISCALES


class Migration(migrations.Migration):
    dependencies = [("facturacion", "0010_item_unidad_pz")]

    operations = [
        migrations.AlterField(
            model_name="factura",
            name="regimen_fiscal",
            field=models.CharField(
                choices=REGIMENES_FISCALES, db_index=True,
                default="honorarios", max_length=12,
            ),
        ),
    ]
