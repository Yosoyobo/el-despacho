"""S-Proyecto-Estados-V1: modelo EstadoProyecto configurable + seed de los 7
estados base + AlterField a `Proyecto.estado` para liberar choices.

Tras esta migración los slugs siguen siendo válidos (las filas existentes
no se mueven), pero la validación de label/color/terminal vive en DB.
"""

from django.db import migrations, models

ESTADOS_BASE = (
    ("por_cotizar",            "Por cotizar",            "badge-blue",     10, False),
    ("esperando_respuesta",    "Esperando respuesta",    "badge-orange",   20, False),
    ("en_proceso_diseno",      "En proceso de diseño",   "badge-warning",  30, False),
    ("en_proceso_produccion",  "En proceso de producción", "badge-warning", 40, False),
    ("entregado",              "Entregado",              "badge-success",  50, True),
    ("en_pausa",               "En pausa",               "badge-gray",     60, False),
    ("cancelado",              "Cancelado",              "badge-error",    70, True),
)


def seed(apps, schema_editor):
    EstadoProyecto = apps.get_model("proyectos", "EstadoProyecto")
    for slug, label, color, orden, terminal in ESTADOS_BASE:
        EstadoProyecto.objects.update_or_create(
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


def desiembra(apps, schema_editor):
    EstadoProyecto = apps.get_model("proyectos", "EstadoProyecto")
    EstadoProyecto.objects.filter(sistema=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("proyectos", "0006_slug_desde_nombre"),
    ]

    operations = [
        migrations.CreateModel(
            name="EstadoProyecto",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=32, unique=True)),
                ("label", models.CharField(max_length=64)),
                ("color", models.CharField(default="badge-gray", max_length=24, choices=[
                    ("badge-blue", "Azul"),
                    ("badge-orange", "Naranja"),
                    ("badge-warning", "Amarillo"),
                    ("badge-success", "Verde"),
                    ("badge-error", "Rojo"),
                    ("badge-gray", "Gris"),
                    ("badge-brand", "Brand"),
                ])),
                ("orden", models.PositiveSmallIntegerField(default=100)),
                ("terminal", models.BooleanField(default=False, help_text="Si está marcado, el proyecto se considera cerrado.")),
                ("activo", models.BooleanField(default=True)),
                ("sistema", models.BooleanField(default=False, help_text="Sembrado por código; no se puede borrar.")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "proyectos_estado",
                "verbose_name": "estado de proyecto",
                "verbose_name_plural": "estados de proyecto",
                "ordering": ["orden", "label"],
            },
        ),
        migrations.AlterField(
            model_name="proyecto",
            name="estado",
            field=models.CharField(default="por_cotizar", max_length=32, db_index=True),
        ),
        migrations.RunPython(seed, desiembra),
    ]
