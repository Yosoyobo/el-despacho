"""S-LC-Buzon-V2: modelo TipoBuzon configurable + seed de los 3 tipos base
+ AlterField a `MensajeBuzon.tipo` para liberar choices (espejo de
0004_estado_buzon). Las filas existentes no se mueven (los slugs
sugerencia/problema/otro siguen siendo válidos)."""

import django.core.validators
from django.db import migrations, models

TIPOS_BASE = (
    ("sugerencia", "Sugerencia",     "#465fff", 10),
    ("problema",   "Problema / bug", "#f04438", 20),
    ("otro",       "Otro",           "#667085", 30),
)


def seed(apps, schema_editor):
    TipoBuzon = apps.get_model("buzon", "TipoBuzon")
    for slug, label, color, orden in TIPOS_BASE:
        TipoBuzon.objects.update_or_create(
            slug=slug,
            defaults={"label": label, "color": color, "orden": orden, "activo": True, "sistema": True},
        )


def desiembra(apps, schema_editor):
    TipoBuzon = apps.get_model("buzon", "TipoBuzon")
    TipoBuzon.objects.filter(sistema=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("buzon", "0005_lectura_buzon"),
    ]

    operations = [
        migrations.CreateModel(
            name="TipoBuzon",
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
                ("activo", models.BooleanField(default=True)),
                ("sistema", models.BooleanField(default=False, help_text="Sembrado por código; no se puede borrar.")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "buzon_tipo",
                "verbose_name": "tipo del Buzón",
                "verbose_name_plural": "tipos del Buzón",
                "ordering": ["orden", "label"],
            },
        ),
        migrations.AlterField(
            model_name="mensajebuzon",
            name="tipo",
            field=models.CharField(db_index=True, max_length=32),
        ),
        migrations.RunPython(seed, desiembra),
    ]
