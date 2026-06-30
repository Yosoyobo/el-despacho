from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('el_catalogo', '0007_proveedor_direccion_fiscal'),
    ]

    operations = [
        migrations.AddField(
            model_name='proveedor',
            name='lat',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='proveedor',
            name='lng',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
