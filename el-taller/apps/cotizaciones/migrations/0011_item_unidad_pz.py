"""Sprint Fiscal 2026-07 (#12) — unidad consolidada a 'pz'.

Cambia el default de `CotizacionItem.unidad` de "pieza" a "pz". Cambio de
default a nivel Python; no toca datos existentes.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0010_regimen_fiscal"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cotizacionitem",
            name="unidad",
            field=models.CharField(default="pz", max_length=30),
        ),
    ]
