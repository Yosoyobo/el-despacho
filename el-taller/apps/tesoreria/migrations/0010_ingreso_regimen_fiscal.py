# Oscar 2026-10-14: el ingreso recuerda con qué esquema fiscal se desglosó
# (IVA 16% / RESICO con retenciones / sin IVA). Sólo esquema: no mueve datos.
# Los registros existentes quedan en '' y se deducen de `incluye_iva`.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tesoreria', '0009_egreso_origen_cfdi'),
    ]

    operations = [
        migrations.AddField(
            model_name='ingreso',
            name='regimen_fiscal',
            field=models.CharField(blank=True, default='', max_length=12),
        ),
    ]
