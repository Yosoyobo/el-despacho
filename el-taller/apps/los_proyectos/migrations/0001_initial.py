from django.conf import settings
from django.db import migrations, models

import apps.los_proyectos.models.proyecto


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("cartera", "0001_initial"),
        ("cuentas", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Proyecto",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "codigo",
                    models.CharField(
                        db_index=True,
                        default=apps.los_proyectos.models.proyecto.generar_codigo_proyecto,
                        max_length=12,
                        unique=True,
                    ),
                ),
                ("nombre", models.CharField(max_length=200)),
                ("descripcion", models.TextField(blank=True, default="")),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("prospecto", "Prospecto"),
                            ("cotizado", "Cotizado"),
                            ("en_diseno", "En diseño"),
                            ("revision_cliente", "Revisión cliente"),
                            ("en_produccion", "En producción"),
                            ("entregado", "Entregado"),
                            ("en_pausa", "En pausa"),
                            ("cancelado", "Cancelado"),
                        ],
                        db_index=True,
                        default="prospecto",
                        max_length=20,
                    ),
                ),
                ("fecha_inicio", models.DateField(blank=True, null=True)),
                ("fecha_compromiso", models.DateField(blank=True, null=True)),
                ("fecha_real_entrega", models.DateField(blank=True, null=True)),
                ("monto_estimado", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=models.deletion.PROTECT,
                        related_name="proyectos",
                        to="cartera.cliente",
                    ),
                ),
                (
                    "creado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="proyectos_creados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "proyectos_proyecto",
                "verbose_name": "proyecto",
                "verbose_name_plural": "proyectos",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="ProyectoAsignacion",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "rol_en_proyecto",
                    models.CharField(
                        choices=[
                            ("lider", "Líder"),
                            ("disenador", "Diseñador"),
                            ("produccion", "Producción"),
                            ("revisor", "Revisor"),
                        ],
                        default="disenador",
                        max_length=20,
                    ),
                ),
                ("asignado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "proyecto",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="asignaciones",
                        to="proyectos.proyecto",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="asignaciones_proyecto",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "proyectos_asignacion",
                "verbose_name": "asignación",
                "verbose_name_plural": "asignaciones",
            },
        ),
        migrations.AddConstraint(
            model_name="proyectoasignacion",
            constraint=models.UniqueConstraint(
                fields=("proyecto", "usuario"),
                name="proyectos_asignacion_unica",
            ),
        ),
    ]
