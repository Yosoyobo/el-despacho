"""S-LC-Feedback-V6 Bloque 7C: campañas de correo masivo con auditoría por
destinatario."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("cartera", "0004_cliente_direccion_fiscal"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CampanaCorreo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plantilla_slug", models.CharField(max_length=40)),
                ("asunto_custom", models.CharField(blank=True, default="", max_length=200)),
                ("mensaje_custom", models.TextField(blank=True, default="")),
                ("total_destinatarios", models.PositiveIntegerField(default=0)),
                ("enviados", models.PositiveIntegerField(default=0)),
                ("fallidos", models.PositiveIntegerField(default=0)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True,
                                                 on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="campanas_creadas",
                                                 to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "campanas_correo",
                "ordering": ["-creado_en"],
                "verbose_name": "campaña de correo",
                "verbose_name_plural": "campañas de correo",
            },
        ),
        migrations.CreateModel(
            name="CampanaEnvio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                ("estado", models.CharField(choices=[("enviado", "Enviado"), ("fallido", "Fallido")],
                                            default="enviado", max_length=10)),
                ("error", models.CharField(blank=True, default="", max_length=300)),
                ("enviado_en", models.DateTimeField(auto_now_add=True)),
                ("campana", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="envios", to="campanas.campanacorreo")),
                ("cliente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name="envios_campana", to="cartera.cliente")),
            ],
            options={"db_table": "campanas_envio", "ordering": ["pk"]},
        ),
    ]
