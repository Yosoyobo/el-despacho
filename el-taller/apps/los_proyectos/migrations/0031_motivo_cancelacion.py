"""LC 2026-08-07 (Oscar) — por qué se canceló un proyecto.

Crea el catálogo de motivos (editable en La Gerencia → Catálogos) con los 4 de
arranque, y le cuelga al proyecto el motivo elegido, la nota libre y la fecha en
que se canceló. Todo es opcional: un proyecto ya cancelado se queda sin motivo
hasta que alguien lo complete desde Estadísticas de cancelación.
"""

import django.db.models.deletion
from django.db import migrations, models


def sembrar_motivos(apps, schema_editor):
    Motivo = apps.get_model("proyectos", "MotivoCancelacion")
    base = (
        ("precio", "Precio", 10),
        ("cliente_desistio", "Cliente desistió", 20),
        ("tiempos", "Tiempos", 30),
        ("otro", "Otro", 90),
    )
    for slug, label, orden in base:
        Motivo.objects.update_or_create(
            slug=slug,
            defaults={"label": label, "orden": orden, "activo": True, "sistema": True},
        )


def borrar_motivos(apps, schema_editor):
    apps.get_model("proyectos", "MotivoCancelacion").objects.filter(sistema=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("proyectos", "0030_ajustes_ago04_r3"),
    ]

    operations = [
        migrations.CreateModel(
            name="MotivoCancelacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=40, unique=True)),
                ("label", models.CharField(max_length=60)),
                ("orden", models.PositiveIntegerField(default=0)),
                ("activo", models.BooleanField(default=True)),
                ("sistema", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name": "motivo de cancelación",
                "verbose_name_plural": "motivos de cancelación",
                "db_table": "proyectos_motivo_cancelacion",
                "ordering": ["orden", "label"],
            },
        ),
        migrations.AddField(
            model_name="proyecto",
            name="motivo_cancelacion",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="proyectos",
                to="proyectos.motivocancelacion",
            ),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="nota_cancelacion",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="cancelado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(sembrar_motivos, borrar_motivos),
    ]
