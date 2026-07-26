"""Régimen fiscal por default = «IVA y Retenciones» (Oscar 2026-07-25).

Solo cambia el default del campo: los proyectos que ya existen conservan el
régimen con el que se capturaron. Aplica al alta por formulario y, sobre todo,
al alta por El Chalán, que crea el modelo directo y por eso venía naciendo en
régimen 'iva' (sin retenciones).
"""

from django.db import migrations, models

from lib.fiscal import REGIMENES_FISCALES


class Migration(migrations.Migration):
    # El app_label es `proyectos` (no `los_proyectos`), igual que en el resto
    # de las migraciones de esta app.
    dependencies = [("proyectos", "0024_producto_nombre_proyecto")]

    operations = [
        migrations.AlterField(
            model_name="proyecto",
            name="regimen_fiscal",
            field=models.CharField(
                choices=REGIMENES_FISCALES, db_index=True,
                default="honorarios", max_length=12,
            ),
        ),
    ]
