from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartera', '0003_cliente_contacto'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='direccion_fiscal',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='cliente',
            name='fiscal_igual',
            field=models.BooleanField(default=True, help_text='La dirección fiscal es la misma que la dirección.'),
        ),
    ]
