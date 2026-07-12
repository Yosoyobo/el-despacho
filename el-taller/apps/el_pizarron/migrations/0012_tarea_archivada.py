"""LC #154 — soft-hide de tareas (archivar reversible, sigue en métricas)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pizarron", "0011_tarea_responsables"),
    ]

    operations = [
        migrations.AddField(
            model_name="tarea",
            name="archivada",
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
