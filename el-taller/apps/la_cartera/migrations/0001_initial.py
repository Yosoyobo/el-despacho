from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("cuentas", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Cliente",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("razon_social", models.CharField(db_index=True, max_length=200)),
                ("rfc", models.CharField(blank=True, db_index=True, default="", max_length=13)),
                ("nombre_contacto", models.CharField(blank=True, default="", max_length=200)),
                ("email_contacto", models.EmailField(blank=True, default="", max_length=254)),
                ("telefono", models.CharField(blank=True, default="", max_length=40)),
                ("direccion", models.TextField(blank=True, default="")),
                ("notas", models.TextField(blank=True, default="")),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("prospecto", "Prospecto"),
                            ("activo", "Activo"),
                            ("inactivo", "Inactivo"),
                        ],
                        db_index=True,
                        default="prospecto",
                        max_length=20,
                    ),
                ),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "creado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="clientes_creados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "cartera_cliente",
                "verbose_name": "cliente",
                "verbose_name_plural": "clientes",
                "ordering": ["razon_social"],
            },
        ),
        migrations.AddConstraint(
            model_name="cliente",
            constraint=models.UniqueConstraint(
                condition=~models.Q(rfc=""),
                fields=("rfc",),
                name="cartera_cliente_rfc_unique_nonempty",
            ),
        ),
    ]
