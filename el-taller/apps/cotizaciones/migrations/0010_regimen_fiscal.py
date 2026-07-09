from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0009_estado_anticipo"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacion",
            name="regimen_fiscal",
            field=models.CharField(
                choices=[
                    ("iva", "IVA (16%)"),
                    ("honorarios", "IVA y Retenciones"),
                    ("exento", "Exento"),
                ],
                default="iva",
                db_index=True,
                max_length=12,
            ),
        ),
    ]
