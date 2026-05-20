from django.conf import settings
from django.db import migrations, models


def _seed_estacion_kpi_dsl(apps, schema_editor):
    """Seed estación 'kpi_dsl' en CuadroChalanes para que el Chalán Claudio
    atienda las peticiones de NL→DSL al crear KPIs custom (S2b.5)."""
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    CuadroChalanes.objects.update_or_create(
        estacion="kpi_dsl",
        defaults={
            "proveedor": "anthropic",
            "modelo": "claude-opus-4-7",
            "descripcion": "Traduce NL→DSL JSON para KPIs personalizados (S2b.5).",
        },
    )


def _unseed_estacion_kpi_dsl(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    CuadroChalanes.objects.filter(estacion="kpi_dsl").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("taller_home", "0001_initial"),
        ("chalanes", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="KPICustom",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("titulo", models.CharField(max_length=100)),
                ("descripcion", models.TextField(blank=True, default="")),
                ("definicion_json", models.JSONField()),
                ("alcance", models.CharField(
                    choices=[("personal", "Personal — sólo yo lo veo"),
                             ("equipo", "Equipo — visible a todo el despacho")],
                    default="personal", max_length=20,
                )),
                ("categoria", models.CharField(default="custom", max_length=30)),
                ("estado", models.CharField(
                    choices=[("activo", "Activo"),
                             ("pendiente_aprobacion", "Pendiente de aprobación"),
                             ("rechazado", "Rechazado"),
                             ("archivado", "Archivado por el autor")],
                    db_index=True, default="activo", max_length=30,
                )),
                ("aprobado_en", models.DateTimeField(blank=True, null=True)),
                ("motivo_rechazo", models.CharField(blank=True, default="", max_length=300)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("autor", models.ForeignKey(
                    null=True, on_delete=models.deletion.SET_NULL,
                    related_name="kpis_custom_creados", to=settings.AUTH_USER_MODEL,
                )),
                ("aprobado_por", models.ForeignKey(
                    blank=True, null=True, on_delete=models.deletion.SET_NULL,
                    related_name="kpis_custom_aprobados", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "taller_home_kpi_custom",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="kpicustom",
            index=models.Index(fields=["alcance", "estado"], name="kpicust_alcance_est_idx"),
        ),
        migrations.AddIndex(
            model_name="kpicustom",
            index=models.Index(fields=["autor", "estado"], name="kpicust_autor_est_idx"),
        ),
        migrations.RunPython(_seed_estacion_kpi_dsl, _unseed_estacion_kpi_dsl),
    ]
