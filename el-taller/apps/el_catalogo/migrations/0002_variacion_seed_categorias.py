"""Sprint S-LC-Feedback-V1: nuevo modelo Variacion + seed de categorías
solicitadas por LC (Diseño / Impresión / Producción / Diseño + Producción)."""

from django.db import migrations, models


CATEGORIAS_LC = [
    ("Diseño", 10),
    ("Impresión", 20),
    ("Producción", 30),
    ("Diseño + Producción", 40),
]


def sembrar_categorias(apps, schema_editor):
    Cat = apps.get_model("el_catalogo", "CategoriaServicio")
    for nombre, orden in CATEGORIAS_LC:
        Cat.objects.update_or_create(
            nombre=nombre,
            defaults={"orden": orden, "activa": True},
        )


def revertir(apps, schema_editor):
    # No borramos las categorías — pueden tener servicios asignados.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Variacion",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("nombre", models.CharField(max_length=150)),
                ("costo", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("impresion_activa", models.BooleanField(default=False)),
                (
                    "impresion_costo",
                    models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=12),
                ),
                ("impresion_descripcion", models.CharField(blank=True, default="", max_length=250)),
                ("descripcion", models.CharField(blank=True, default="", max_length=500)),
                ("disponible", models.BooleanField(db_index=True, default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "servicio",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="variaciones",
                        to="el_catalogo.servicio",
                    ),
                ),
            ],
            options={
                "db_table": "catalogo_variacion",
                "ordering": ["servicio__nombre", "nombre"],
                "verbose_name": "variación",
                "verbose_name_plural": "variaciones",
            },
        ),
        migrations.RunPython(sembrar_categorias, revertir),
    ]
