"""S-LC-Feedback-V12: directorio de Sedes/POI de LC (SedeLC) + modo de geocerca
global (ConfiguracionGeocerca, singleton). Solo crea tablas; el modo default es
'libre' (no valida ubicación) para no sorprender a nadie al desplegar."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("checador", "0006_jornada_minutos_extra"),
    ]

    operations = [
        migrations.CreateModel(
            name="SedeLC",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(help_text="Ej. Oficina 1, Taller Cuajimalpa.", max_length=120)),
                ("direccion", models.TextField(blank=True, default="", help_text="Dirección visible.")),
                ("lat", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("lng", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("radio_m", models.PositiveIntegerField(default=150, help_text="Radio de la geocerca en metros desde el pin.")),
                ("activa", models.BooleanField(default=True, help_text="Si está activa, cuenta como ubicación válida.")),
                ("orden", models.PositiveSmallIntegerField(default=100)),
                ("notas", models.TextField(blank=True, default="")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "sede de LC",
                "verbose_name_plural": "sedes de LC",
                "db_table": "checador_sede",
                "ordering": ["orden", "nombre"],
            },
        ),
        migrations.CreateModel(
            name="ConfiguracionGeocerca",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("modo", models.CharField(
                    choices=[
                        ("libre", "Modo Libre — no valida ubicación"),
                        ("restringido", "Modo Restringido — anota las checadas fuera de sede"),
                    ],
                    default="libre", max_length=12)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "configuración de geocerca",
                "verbose_name_plural": "configuración de geocerca",
                "db_table": "checador_config_geocerca",
            },
        ),
    ]
