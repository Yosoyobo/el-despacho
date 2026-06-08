"""S-Buzon-Estados-V1: modelo EstadoBuzon configurable + seed de los 4
estados base + AlterField a `MensajeBuzon.estado` para liberar choices.

Las filas existentes no se mueven (los slugs nuevo/leido/respondido/archivado
siguen siendo válidos); la validación de label/color/terminal vive en DB.
"""

import django.core.validators
from django.db import migrations, models

ESTADOS_BASE = (
    ("nuevo",      "Nuevo",      "#0ba5ec", 10, False),
    ("leido",      "Leído",      "#465fff", 20, False),
    ("respondido", "Respondido", "#12b76a", 30, False),
    ("archivado",  "Archivado",  "#7a5af8", 40, True),
)


def seed(apps, schema_editor):
    EstadoBuzon = apps.get_model("buzon", "EstadoBuzon")
    for slug, label, color, orden, terminal in ESTADOS_BASE:
        EstadoBuzon.objects.update_or_create(
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
    EstadoBuzon = apps.get_model("buzon", "EstadoBuzon")
    EstadoBuzon.objects.filter(sistema=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("buzon", "0003_mensaje_buzon_adjunto"),
    ]

    operations = [
        migrations.CreateModel(
            name="EstadoBuzon",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=32, unique=True)),
                ("label", models.CharField(max_length=64)),
                ("color", models.CharField(
                    default="#667085", max_length=7,
                    help_text="Color HEX del badge, ej. #465fff.",
                    validators=[django.core.validators.RegexValidator(
                        message="Usa un color hexadecimal de 6 dígitos, ej. #465fff.",
                        regex=r"^#[0-9a-fA-F]{6}$",
                    )],
                )),
                ("orden", models.PositiveSmallIntegerField(default=100)),
                ("terminal", models.BooleanField(default=False, help_text="Si está marcado, el ticket se considera cerrado.")),
                ("activo", models.BooleanField(default=True)),
                ("sistema", models.BooleanField(default=False, help_text="Sembrado por código; no se puede borrar.")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "buzon_estado",
                "verbose_name": "estado del Buzón",
                "verbose_name_plural": "estados del Buzón",
                "ordering": ["orden", "label"],
            },
        ),
        migrations.AlterField(
            model_name="mensajebuzon",
            name="estado",
            field=models.CharField(default="nuevo", max_length=20, db_index=True),
        ),
        migrations.RunPython(seed, desiembra),
    ]
