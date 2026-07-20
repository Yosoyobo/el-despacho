"""Sprint Fiscal 2026-07 (#12) — unidad consolidada a 'pz'.

Cambia el default de `Servicio.unidad` de "pieza" a "pz". Es un cambio de
default a nivel Python (no toca datos existentes); los productos nuevos nacen
en 'pz'. La columna se conserva (sin selector en la UI).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0010_servicio_imagen"),
    ]

    operations = [
        migrations.AlterField(
            model_name="servicio",
            name="unidad",
            field=models.CharField(default="pz", max_length=30),
        ),
    ]
