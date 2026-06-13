"""S-LC-Feedback-V8 — avatar subido por el usuario (Drive privado + proxy)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0026_usuario_jefe_geocerca"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="avatar_drive_id",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
