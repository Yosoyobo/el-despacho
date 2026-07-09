from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion", "0007_folio_porcentaje"),
    ]

    operations = [
        migrations.AddField(
            model_name="factura",
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
