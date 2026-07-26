"""LC 2026-07-26 (Oscar) — foto por USO del producto.

La imagen se sube (o se pega) desde la tarjeta del producto en la página del
proyecto. Si la línea tiene alias, la foto es de ese uso y vive aquí; si no, se
guarda en el catálogo. Aditiva: vacío = se sigue usando la del catálogo.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0025_regimen_default_honorarios"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyectoproducto",
            name="imagen_file_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="proyectoproducto",
            name="imagen_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]
