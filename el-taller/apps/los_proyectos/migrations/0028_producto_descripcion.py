"""LC 2026-08-04 (Oscar) — la «nota corta» de la línea de producto pasa a ser su
DESCRIPCIÓN: la especificación del elemento que viaja a la cotización.

Deja de ser un renglón de 200 caracteres y acepta varias líneas. El nombre del
campo se conserva (`nota`) para no arrastrar un rename por todo el repo — undo,
duplicar proyecto y el mini-Chalán lo leen por ese nombre. Los datos no se tocan:
`CharField` → `TextField` sobre Postgres es un `ALTER TYPE` que preserva el
contenido.

Escrita a mano: `makemigrations` agrega operaciones espurias (los `AlterField id`
de BigAutoField y un rename de índice) que no son de este sprint.
"""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0027_producto_venta"),
    ]

    operations = [
        migrations.AlterField(
            model_name="proyectoproducto",
            name="nota",
            field=models.TextField(blank=True, default=""),
        ),
    ]
