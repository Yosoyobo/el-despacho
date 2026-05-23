"""S-LC-Feedback-V2: modelo Unidad + seed inicial (Piezas, Metros)."""

from django.db import migrations, models

SEED_UNIDADES = [
    ("Piezas", "pz", 10),
    ("Metros", "m", 20),
]


def sembrar(apps, schema_editor):
    Unidad = apps.get_model("el_catalogo", "Unidad")
    for nombre, abrev, orden in SEED_UNIDADES:
        Unidad.objects.update_or_create(
            nombre=nombre,
            defaults={"abreviacion": abrev, "orden": orden, "activa": True},
        )


def revertir(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0002_variacion_seed_categorias"),
    ]

    operations = [
        migrations.CreateModel(
            name="Unidad",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("nombre", models.CharField(max_length=30, unique=True)),
                ("abreviacion", models.CharField(max_length=10, blank=True, default="")),
                ("orden", models.PositiveSmallIntegerField(default=10, db_index=True)),
                ("activa", models.BooleanField(default=True, db_index=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "catalogo_unidad",
                "ordering": ["orden", "nombre"],
                "verbose_name": "unidad de medida",
                "verbose_name_plural": "unidades de medida",
            },
        ),
        migrations.RunPython(sembrar, revertir),
    ]
