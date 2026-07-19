# Fase 3 (§2): comprobante del ingreso en Drive (espejo de Egreso).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tesoreria', '0007_egreso_metodo_efectivo_personal'),
    ]

    operations = [
        migrations.AddField(
            model_name='ingreso',
            name='drive_file_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='ingreso',
            name='drive_url_view',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='ingreso',
            name='tiene_comprobante',
            field=models.BooleanField(default=False),
        ),
    ]
