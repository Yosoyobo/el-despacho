"""S-LC-Feedback-V9 — carpeta/grupo personalizado por usuario en el sidebar."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0027_usuario_avatar_drive_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="sidebarordenusuario",
            name="grupo",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
    ]
