"""Folio oficial «F###» + parcialidad a facturar + título opcional.

LC 2026-07: el folio F es la foliación visible de las facturas; el título se
retira del formulario y se autollena con el concepto; el porcentaje_a_facturar
soporta la pill 100%/50% escalando el monto sin tocar las líneas.
"""

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion", "0006_recordatoriocobranza"),
    ]

    operations = [
        migrations.AddField(
            model_name="factura",
            name="folio_numero",
            field=models.PositiveIntegerField(
                blank=True, null=True, unique=True, db_index=True
            ),
        ),
        migrations.AddField(
            model_name="factura",
            name="porcentaje_a_facturar",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("100.00"), max_digits=5
            ),
        ),
        migrations.AlterField(
            model_name="factura",
            name="titulo",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
