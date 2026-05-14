from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("proyectos", "0001_initial"),
        ("cuentas", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Tarea",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("titulo", models.CharField(max_length=200)),
                ("descripcion", models.TextField(blank=True, default="")),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("pendiente", "Pendiente"),
                            ("en_curso", "En curso"),
                            ("bloqueada", "Bloqueada"),
                            ("completada", "Completada"),
                        ],
                        db_index=True,
                        default="pendiente",
                        max_length=20,
                    ),
                ),
                (
                    "prioridad",
                    models.CharField(
                        choices=[("baja", "Baja"), ("media", "Media"), ("alta", "Alta")],
                        default="media",
                        max_length=10,
                    ),
                ),
                ("fecha_compromiso", models.DateField(blank=True, null=True)),
                ("completada_en", models.DateTimeField(blank=True, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "proyecto",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="tareas",
                        to="proyectos.proyecto",
                    ),
                ),
                (
                    "asignada_a",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="tareas_asignadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "creado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="tareas_creadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "pizarron_tarea",
                "verbose_name": "tarea",
                "verbose_name_plural": "tareas",
                "ordering": ["estado", "-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="Comentario",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("cuerpo", models.TextField()),
                ("es_interno", models.BooleanField(db_index=True, default=False)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "autor",
                    models.ForeignKey(
                        on_delete=models.deletion.PROTECT,
                        related_name="comentarios",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "proyecto",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.CASCADE,
                        related_name="comentarios",
                        to="proyectos.proyecto",
                    ),
                ),
                (
                    "tarea",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.CASCADE,
                        related_name="comentarios",
                        to="pizarron.tarea",
                    ),
                ),
            ],
            options={
                "db_table": "pizarron_comentario",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.AddConstraint(
            model_name="comentario",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(tarea__isnull=False, proyecto__isnull=True)
                    | models.Q(tarea__isnull=True, proyecto__isnull=False)
                ),
                name="pizarron_comentario_uno_de_dos",
            ),
        ),
    ]
