"""S-LC-Feedback-V6 Bloque 1B: modelo EstadoTarea configurable (espejo del
patrón S-Proyecto-Estados-V1) + AlterField a `Tarea.estado` para liberar
choices + seed de los 3 estados base + migración de datos
`bloqueada` → `pendiente` ("Bloqueada" se elimina; "Atrasada" es derivada,
no almacenada)."""

from django.db import migrations, models

ESTADOS_TAREA_BASE = (
    ("pendiente",  "Pendiente",  "#0ba5ec", 10, False),
    ("en_curso",   "En curso",   "#465fff", 20, False),
    ("completada", "Completada", "#12b76a", 30, True),
)


def seed(apps, schema_editor):
    EstadoTarea = apps.get_model("pizarron", "EstadoTarea")
    for slug, label, color, orden, terminal in ESTADOS_TAREA_BASE:
        EstadoTarea.objects.update_or_create(
            slug=slug,
            defaults={
                "label": label,
                "color": color,
                "orden": orden,
                "terminal": terminal,
                "activo": True,
                "sistema": True,
            },
        )
    # bloqueada deja de existir como estado almacenado.
    Tarea = apps.get_model("pizarron", "Tarea")
    Tarea.objects.filter(estado="bloqueada").update(estado="pendiente")


def desiembra(apps, schema_editor):
    EstadoTarea = apps.get_model("pizarron", "EstadoTarea")
    EstadoTarea.objects.filter(sistema=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("pizarron", "0003_tarea_tipo_hora"),
    ]

    operations = [
        migrations.CreateModel(
            name="EstadoTarea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=32, unique=True)),
                ("label", models.CharField(max_length=64)),
                ("color", models.CharField(default="#667085", max_length=7,
                                           help_text="Color HEX del badge, ej. #465fff.")),
                ("orden", models.PositiveSmallIntegerField(default=100)),
                ("terminal", models.BooleanField(default=False, help_text="Si está marcado, la tarea se considera cerrada.")),
                ("activo", models.BooleanField(default=True)),
                ("sistema", models.BooleanField(default=False, help_text="Sembrado por código; no se puede borrar.")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "pizarron_estado",
                "verbose_name": "estado de tarea",
                "verbose_name_plural": "estados de tarea",
                "ordering": ["orden", "label"],
            },
        ),
        migrations.AlterField(
            model_name="tarea",
            name="estado",
            field=models.CharField(default="pendiente", max_length=32, db_index=True),
        ),
        migrations.RunPython(seed, desiembra),
    ]
