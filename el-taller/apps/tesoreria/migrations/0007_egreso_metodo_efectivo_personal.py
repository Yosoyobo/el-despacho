from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tesoreria", "0006_egreso_origen_proyecto"),
    ]

    operations = [
        migrations.AlterField(
            model_name="egreso",
            name="metodo",
            field=models.CharField(
                choices=[
                    ("transferencia", "Transferencia empresa"),
                    ("tarjeta_empresa", "Tarjeta empresa"),
                    ("tarjeta_personal", "Tarjeta personal (reembolso)"),
                    ("efectivo_personal", "Efectivo personal (reembolso)"),
                    ("efectivo", "Efectivo"),
                    ("cheque", "Cheque"),
                    ("otro", "Otro"),
                ],
                default="transferencia",
                max_length=30,
            ),
        ),
    ]
