from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ajustes", "0010_correo_auto"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracionfiscal",
            name="ret_isr_honorarios",
            field=models.DecimalField(
                decimal_places=3, default=Decimal("1.250"), max_digits=6,
                help_text="% de retención de ISR sobre el importe (RESICO/honorarios: 1.25%).",
            ),
        ),
        migrations.AddField(
            model_name="configuracionfiscal",
            name="ret_iva_honorarios_num",
            field=models.PositiveSmallIntegerField(
                default=2,
                help_text="Numerador de la retención de IVA como fracción del IVA trasladado (⅔ → 2).",
            ),
        ),
        migrations.AddField(
            model_name="configuracionfiscal",
            name="ret_iva_honorarios_den",
            field=models.PositiveSmallIntegerField(
                default=3,
                help_text="Denominador de la retención de IVA como fracción del IVA trasladado (⅔ → 3).",
            ),
        ),
    ]
