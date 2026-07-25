"""LC 2026-07 (Oscar) — alias del producto DENTRO del proyecto.

El despacho compra «TShirt Oversize Color» a Crea Blanks y la vende como
«TShirt Modelo Janet». Este campo guarda ese nombre de venta para el proyecto
y la cotización, sin perder el FK al producto del catálogo (de qué está hecho
y a quién se le compra). Aditiva: vacío = se sigue usando el nombre del
catálogo, así que los proyectos existentes no cambian.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0023_proyectoproducto_orden"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyectoproducto",
            name="nombre_proyecto",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Cómo se llama este producto en este proyecto. "
                    "Vacío = el nombre del catálogo."
                ),
                max_length=150,
            ),
        ),
    ]
