"""La tarea recuerda de qué línea de producto salió (LC 2026-08-28, nota 6).

Sólo `AddField`. Nada que sembrar: las tareas que ya existen se quedan sin
producto, que es la verdad — no salieron de una tarjeta.

Ojo con los `app_label`: el de las tareas es `pizarron` y el de los proyectos
es `proyectos` (no `el_pizarron` / `los_proyectos`). La FK por cadena y la
dependencia usan ésos.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pizarron", "0015_ruta"),
        ("proyectos", "0037_recolorear_tarjetas"),
    ]

    operations = [
        migrations.AddField(
            model_name="tarea",
            name="producto",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tareas",
                to="proyectos.proyectoproducto",
                help_text="La línea de producto de la que salió esta tarea, si salió de una.",
            ),
        ),
    ]
