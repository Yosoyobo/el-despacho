"""El egreso puede nacer de la factura que mandó un proveedor (S-Pendientes-Sep28).

Sólo cambia las opciones de `origen`: no toca la base. Escrita a mano porque
`makemigrations` arrastra otros cambios de estado que no son de este sprint.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tesoreria", "0008_ingreso_comprobante"),
    ]

    operations = [
        migrations.AlterField(
            model_name="egreso",
            name="origen",
            field=models.CharField(
                choices=[
                    ("manual", "Captura manual"),
                    ("ocr", "OCR de recibo"),
                    ("dictado", "Dictado El Chalán"),
                    ("sala_juntas", "Dictado desde Sala de Juntas"),
                    ("proyecto", "Gasto de proyecto (producción)"),
                    ("cfdi", "CFDI de proveedor"),
                ],
                default="manual", max_length=20,
            ),
        ),
    ]
