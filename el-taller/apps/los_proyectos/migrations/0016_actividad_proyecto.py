"""S-Recados-V2 (C5b): feed de actividad por proyecto."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("proyectos", "0015_producto_egreso"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActividadProyecto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(db_index=True, max_length=24, choices=[
                    ("estado_cambiado", "Cambio de estado"),
                    ("tarea_creada", "Nueva tarea"),
                    ("comentario", "Comentario"),
                    ("fecha_por_vencer", "Fecha por vencer"),
                    ("egreso_generado", "Egreso generado"),
                ])),
                ("descripcion", models.CharField(max_length=255)),
                ("url", models.CharField(blank=True, default="", max_length=300)),
                ("creado_en", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="actividades_proyecto", to=settings.AUTH_USER_MODEL)),
                ("proyecto", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="actividades", to="proyectos.proyecto")),
            ],
            options={
                "db_table": "proyectos_actividad",
                "ordering": ["-creado_en"],
                "indexes": [models.Index(fields=["proyecto", "-creado_en"], name="proyectos_a_proyect_idx")],
            },
        ),
    ]
