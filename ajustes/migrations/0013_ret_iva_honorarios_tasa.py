"""Sprint Fiscal 2026-07 — retención de IVA como tasa nominal (Anexo 20 SAT).

Agrega `ConfiguracionFiscal.ret_iva_honorarios` (% sobre la Base, default
10.6667%). Reemplaza el atajo fraccionario ⅔ del IVA (num/den) por el cálculo
independiente Base × tasa nominal. Las columnas num/den se conservan dormidas
(no se dropean para no perder históricos ni romper migraciones).

Solo AddField con default — no toca datos existentes; el singleton hereda
10.6667% automáticamente.
"""

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ajustes", "0012_tasa_porcentaje_4_decimales"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracionfiscal",
            name="ret_iva_honorarios",
            field=models.DecimalField(
                max_digits=7,
                decimal_places=4,
                default=Decimal("10.6667"),
                help_text="% de retención de IVA sobre el importe/Base (RESICO/honorarios: 10.6667% = ⅔ del IVA 16%).",
            ),
        ),
    ]
