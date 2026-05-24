from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="factura",
            name="vencida_notificada_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
