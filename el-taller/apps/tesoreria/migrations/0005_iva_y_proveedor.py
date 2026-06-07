"""Sprint S-LC-Buzon: desglose de IVA (subtotal + incluye_iva) en Ingreso y
Egreso, y FK opcional Egreso.proveedor → el_catalogo.Proveedor.

Backfill: subtotal = monto para registros existentes (incluye_iva=False, así
que subtotal == monto y la contabilidad no cambia).
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_subtotal(apps, schema_editor):
    for nombre in ("Ingreso", "Egreso"):
        Modelo = apps.get_model("tesoreria", nombre)
        Modelo.objects.filter(subtotal__isnull=True).update(subtotal=models.F("monto"))


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("tesoreria", "0004_egreso_pagado_desde_egreso_pagado_en"),
        ("el_catalogo", "0005_proveedor"),
    ]

    operations = [
        migrations.AddField(
            model_name="ingreso",
            name="subtotal",
            field=models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="ingreso",
            name="incluye_iva",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="egreso",
            name="subtotal",
            field=models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="egreso",
            name="incluye_iva",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="egreso",
            name="proveedor",
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="egresos", to="el_catalogo.proveedor",
            ),
        ),
        migrations.RunPython(backfill_subtotal, noop),
    ]
