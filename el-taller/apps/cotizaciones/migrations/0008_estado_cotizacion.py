import django.core.validators
from django.db import migrations, models

# Igual que el seed de EstadoProyecto: 4 pasos base como sistema=True.
ESTADOS_SEED = (
    ("generada", "Generada", "#0ba5ec", 10, False),
    ("enviada",  "Enviada",  "#465fff", 20, False),
    ("aprobada", "Aprobada", "#12b76a", 30, False),
    ("pagada",   "Pagada",   "#7a5af8", 40, True),
)


def seed_estados(apps, schema_editor):
    EstadoCotizacion = apps.get_model("cotizaciones", "EstadoCotizacion")
    for slug, label, color, orden, terminal in ESTADOS_SEED:
        EstadoCotizacion.objects.update_or_create(
            slug=slug,
            defaults={
                "label": label, "color": color, "orden": orden,
                "terminal": terminal, "activo": True, "sistema": True,
            },
        )


def unseed(apps, schema_editor):
    EstadoCotizacion = apps.get_model("cotizaciones", "EstadoCotizacion")
    EstadoCotizacion.objects.filter(sistema=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0007_cotizacion_proyecto_version"),
    ]

    operations = [
        migrations.CreateModel(
            name="EstadoCotizacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=32, unique=True)),
                ("label", models.CharField(max_length=64)),
                ("descripcion", models.CharField(blank=True, default="", help_text="Qué significa este paso (ayuda para el equipo).", max_length=200)),
                ("color", models.CharField(default="#667085", help_text="Color HEX del badge/tracker, ej. #465fff.", max_length=7, validators=[django.core.validators.RegexValidator(message="Usa un color hexadecimal de 6 dígitos, ej. #465fff.", regex="^#[0-9a-fA-F]{6}$")])),
                ("orden", models.PositiveSmallIntegerField(default=100)),
                ("terminal", models.BooleanField(default=False, help_text="Paso final del flujo (ej. Pagada).")),
                ("activo", models.BooleanField(default=True)),
                ("sistema", models.BooleanField(default=False, help_text="Sembrado por código; no se puede borrar.")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "estado de cotización",
                "verbose_name_plural": "estados de cotización",
                "db_table": "cotizaciones_estado",
                "ordering": ["orden", "label"],
            },
        ),
        migrations.RunPython(seed_estados, unseed),
    ]
