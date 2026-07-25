"""LC 2026-07 (Oscar) — los dos interruptores del documento del cliente.

- `incluir_desglose`: prendido, el PDF agrega al final el «Desglose de
  Elementos» (todos los conceptos juntos) y el cálculo de impuestos con el
  total. Arranca APAGADO para no cambiar el documento de las cotizaciones que
  ya existen.
- `forma_pago`: elige el texto de la última nota del PDF («Anticipo N%» o
  «Un sólo pago»). Default anticipo, que es como opera LC hoy.

Cada versión de la cotización guarda los suyos; la siguiente versión los
hereda al generarse.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0011_item_unidad_pz"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacion",
            name="incluir_desglose",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Incluir al final del PDF el desglose de conceptos y el "
                    "cálculo de impuestos."
                ),
            ),
        ),
        migrations.AddField(
            model_name="cotizacion",
            name="forma_pago",
            field=models.CharField(
                choices=[("anticipo", "Anticipo"), ("contado", "Un solo pago")],
                default="anticipo",
                help_text="Define la nota de forma de pago del PDF.",
                max_length=12,
            ),
        ),
    ]
