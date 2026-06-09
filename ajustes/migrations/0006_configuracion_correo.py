import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ajustes", "0005_credencial_ultimo_test"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionCorreo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("proveedor", models.CharField(choices=[("n8n", "n8n (vía El Portavoz)"), ("smtp", "SMTP directo")], default="n8n", max_length=10)),
                ("remitente_nombre", models.CharField(blank=True, default="Learning Center", help_text="Nombre visible del remitente (ej. «Learning Center»).", max_length=120)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("actualizado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="config_correo_actualizadas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "configuración de correo",
                "verbose_name_plural": "configuración de correo",
                "db_table": "ajustes_configuracion_correo",
            },
        ),
    ]
