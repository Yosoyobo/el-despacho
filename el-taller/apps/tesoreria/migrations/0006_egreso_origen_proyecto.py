"""Agrega el origen `proyecto` a Egreso (gastos de producción de un proyecto).

Solo AlterField del campo `origen` para sumar la opción al choices — no toca
datos (no-op a nivel DB). Lo usa el signal que genera Egresos al pasar un
proyecto a producción (apps.los_proyectos.signals_egresos).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tesoreria", "0005_iva_y_proveedor"),
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
                ],
                default="manual",
                max_length=20,
            ),
        ),
    ]
