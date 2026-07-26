"""LC 2026-07-26 — foto congelada por línea de cotización.

Al generar la versión se copia la foto del uso del proyecto (o la del catálogo).
Así una versión pasada conserva la imagen con la que se cotizó, aunque después
se le cambie la foto al producto. Aditiva: vacío = se usa la del catálogo.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0015_regimen_default_honorarios"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacionitem",
            name="imagen_file_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
