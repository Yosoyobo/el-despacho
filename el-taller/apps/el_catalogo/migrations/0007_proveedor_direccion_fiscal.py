from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('el_catalogo', '0006_categoria_color'),
    ]

    operations = [
        migrations.AddField(
            model_name='proveedor',
            name='direccion_fiscal',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='proveedor',
            name='fiscal_igual',
            field=models.BooleanField(default=True, help_text='La dirección fiscal es la misma que la dirección.'),
        ),
    ]
