from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PreferenciaKPI",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("kpi_slug", models.CharField(max_length=80)),
                ("visible", models.BooleanField(default=True)),
                ("orden", models.IntegerField(blank=True, null=True)),
                ("origen", models.CharField(default="manual", max_length=20)),
                ("modificado_en", models.DateTimeField(auto_now=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="preferencias_kpi",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "taller_home_preferencia_kpi",
                "unique_together": {("usuario", "kpi_slug")},
            },
        ),
        migrations.AddIndex(
            model_name="preferenciakpi",
            index=models.Index(fields=["usuario", "visible"], name="pref_kpi_user_vis_idx"),
        ),
        migrations.CreateModel(
            name="SugerenciaKPI",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("kpi_slug", models.CharField(max_length=80)),
                ("motivo", models.TextField(blank=True, default="")),
                ("fuente", models.CharField(default="heuristica", max_length=30)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("pendiente", "Pendiente"),
                            ("aceptada", "Aceptada"),
                            ("descartada", "Descartada"),
                        ],
                        default="pendiente",
                        max_length=20,
                    ),
                ),
                ("sugerido_en", models.DateTimeField(auto_now_add=True)),
                ("resuelta_en", models.DateTimeField(blank=True, null=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="sugerencias_kpi",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "taller_home_sugerencia_kpi",
                "ordering": ["-sugerido_en"],
                "unique_together": {("usuario", "kpi_slug")},
            },
        ),
    ]
