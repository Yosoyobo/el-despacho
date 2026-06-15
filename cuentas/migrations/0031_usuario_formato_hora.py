"""S-LC-Feedback-V11 — formato de hora por usuario (24h por defecto / AM-PM)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0030_sidebar_carpeta_usuario"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="formato_hora",
            field=models.CharField(
                choices=[("24h", "24 horas (14:30)"), ("ampm", "AM/PM (2:30 p.m.)")],
                default="24h", max_length=4,
            ),
        ),
    ]
