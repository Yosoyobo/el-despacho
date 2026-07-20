"""Sprint Fiscal 2026-07 (#12) — unidad consolidada a 'pz'.

Cambia el default de `FacturaItem.unidad` de "pieza" a "pz". Cambio de default
a nivel Python; no toca datos existentes.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion", "0009_cfdi_almacenado"),
    ]

    operations = [
        migrations.AlterField(
            model_name="facturaitem",
            name="unidad",
            field=models.CharField(default="pz", max_length=30),
        ),
    ]
