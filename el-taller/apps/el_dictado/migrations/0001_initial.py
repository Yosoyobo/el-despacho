from django.conf import settings
from django.db import migrations, models


def _seed_estacion(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    CuadroChalanes.objects.update_or_create(
        estacion="dictado",
        defaults={
            "proveedor": "anthropic",
            "modelo": "claude-opus-4-7",
            "descripcion": "El Chalán interpreta dictados en lenguaje natural (S2b.2).",
        },
    )


def _unseed_estacion(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    CuadroChalanes.objects.filter(estacion="dictado").delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("chalanes", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Dictado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("texto_crudo", models.TextField()),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("interpretando", "Interpretando con Chalán"),
                            ("esperando_confirmacion", "Esperando confirmación"),
                            ("preguntando", "Chalán pidió clarificación"),
                            ("confirmado_parcial", "Confirmado con subset desmarcado"),
                            ("confirmado_total", "Confirmado todas las acciones"),
                            ("cancelado", "Cancelado por usuario"),
                            ("fallo_ia", "Los Chalanes no disponibles"),
                            ("aplicado", "Acciones ejecutadas"),
                            ("aplicado_con_errores", "Algunas acciones fallaron"),
                        ],
                        db_index=True,
                        default="interpretando",
                        max_length=30,
                    ),
                ),
                (
                    "origen",
                    models.CharField(
                        choices=[
                            ("sala_juntas", "Sala de Juntas del Taller"),
                            ("tesoreria_gasto", "Dictado de gasto en Tesorería"),
                        ],
                        default="sala_juntas",
                        max_length=30,
                    ),
                ),
                ("chalan", models.CharField(blank=True, default="", max_length=30)),
                ("chalan_apodo", models.CharField(blank=True, default="", max_length=50)),
                ("modelo", models.CharField(blank=True, default="", max_length=80)),
                ("interpretacion_raw", models.JSONField(blank=True, default=dict)),
                ("pregunta_clarificacion", models.TextField(blank=True, default="")),
                ("latencia_interpretacion_ms", models.IntegerField(blank=True, null=True)),
                ("costo_usd", models.DecimalField(decimal_places=6, default=0, max_digits=8)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("confirmado_en", models.DateTimeField(blank=True, null=True)),
                ("aplicado_en", models.DateTimeField(blank=True, null=True)),
                (
                    "autor",
                    models.ForeignKey(
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="dictados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "el_dictado_dictado",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="dictado",
            index=models.Index(fields=["autor", "-creado_en"], name="dictado_autor_fecha_idx"),
        ),
        migrations.AddIndex(
            model_name="dictado",
            index=models.Index(fields=["estado"], name="dictado_estado_idx"),
        ),
        migrations.CreateModel(
            name="DictadoAccion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("orden", models.IntegerField()),
                ("tipo", models.CharField(max_length=40)),
                ("descripcion", models.CharField(max_length=300)),
                ("payload", models.JSONField()),
                ("entidad_tipo", models.CharField(blank=True, default="", max_length=30)),
                ("entidad_id", models.BigIntegerField(blank=True, null=True)),
                ("confianza", models.FloatField(default=1.0)),
                ("confirmada", models.BooleanField(default=True)),
                ("aplicada", models.BooleanField(default=False)),
                ("error_al_aplicar", models.TextField(blank=True, default="")),
                ("aplicada_en", models.DateTimeField(blank=True, null=True)),
                (
                    "dictado",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="acciones",
                        to="el_dictado.dictado",
                    ),
                ),
            ],
            options={
                "db_table": "el_dictado_accion",
                "ordering": ["dictado", "orden"],
            },
        ),
        migrations.CreateModel(
            name="DictadoAprendizaje",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("frase_o_patron", models.CharField(max_length=300)),
                ("interpretacion_correcta", models.TextField()),
                ("activo", models.BooleanField(default=True)),
                ("peso", models.FloatField(default=1.0)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("desactivado_en", models.DateTimeField(blank=True, null=True)),
                ("motivo_desactivacion", models.CharField(blank=True, default="", max_length=200)),
                (
                    "autor",
                    models.ForeignKey(
                        null=True, on_delete=models.deletion.SET_NULL,
                        related_name="aprendizajes_que_enseno", to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "desactivado_por",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=models.deletion.SET_NULL,
                        related_name="aprendizajes_desactivados", to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "dictado_origen",
                    models.ForeignKey(
                        null=True, on_delete=models.deletion.SET_NULL,
                        related_name="aprendizajes_generados", to="el_dictado.dictado",
                    ),
                ),
            ],
            options={
                "db_table": "el_dictado_aprendizaje",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="dictadoaprendizaje",
            index=models.Index(fields=["activo", "-creado_en"], name="apr_activo_creado_idx"),
        ),
        migrations.RunPython(_seed_estacion, _unseed_estacion),
    ]
