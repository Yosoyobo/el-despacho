"""LC 2026-08-07 (Oscar): arrastrar tareas en las tablas para ordenarlas.

Sólo agrega la columna del acomodo manual (todas nacen en 0, así que el orden
que ve el equipo hoy no cambia hasta que alguien arrastre una fila) y mete
`orden` al frente del `ordering` del modelo.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pizarron", "0012_tarea_archivada")]

    operations = [
        migrations.AddField(
            model_name="tarea",
            name="orden",
            field=models.IntegerField(db_index=True, default=0),
        ),
        migrations.AlterModelOptions(
            name="tarea",
            options={
                "ordering": ["orden", "estado", "-creado_en"],
                "verbose_name": "tarea",
                "verbose_name_plural": "tareas",
            },
        ),
    ]
