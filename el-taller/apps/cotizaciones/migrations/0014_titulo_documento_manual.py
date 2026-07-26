"""LC 2026-07 (Oscar, segunda ronda) — encabezado del documento editable.

El título centrado del PDF se arma solo con el nombre del proyecto. Ahora se
puede escribir a mano desde la página de la cotización; el campo vacío (el
default) conserva exactamente el comportamiento anterior.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0013_item_concepto"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacion",
            name="titulo_documento_manual",
            field=models.CharField(
                blank=True, default="", max_length=200,
                help_text="Encabezado del PDF. Vacío usa el nombre del proyecto.",
            ),
        ),
    ]
