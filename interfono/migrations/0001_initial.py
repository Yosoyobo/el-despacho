import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InterfonoSuscripcion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("endpoint", models.URLField(max_length=2000, unique=True)),
                ("p256dh", models.CharField(max_length=200)),
                ("auth", models.CharField(max_length=200)),
                ("user_agent", models.CharField(blank=True, default="", max_length=300)),
                ("activa", models.BooleanField(default=True)),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("desactivada_en", models.DateTimeField(blank=True, null=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="suscripciones_push",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "interfono_suscripcion",
                "ordering": ["-creada_en"],
                "indexes": [models.Index(fields=["usuario", "activa"], name="interfono_s_usuario_act_idx")],
            },
        ),
        migrations.CreateModel(
            name="InterfonoEnvio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("audiencia", models.CharField(max_length=40)),
                ("audiencia_label", models.CharField(max_length=120)),
                ("titulo", models.CharField(max_length=80)),
                ("cuerpo", models.CharField(max_length=300)),
                ("url_destino", models.URLField(blank=True, default="")),
                ("entregadas", models.IntegerField(default=0)),
                ("fallidas", models.IntegerField(default=0)),
                ("suscripciones_invalidadas", models.IntegerField(default=0)),
                ("creado_en", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "autor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="envios_interfono",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "interfono_envio",
                "ordering": ["-creado_en"],
            },
        ),
    ]
