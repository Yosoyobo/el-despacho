from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("facturacion", "0003_unidad_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="factura",
            name="concepto",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
