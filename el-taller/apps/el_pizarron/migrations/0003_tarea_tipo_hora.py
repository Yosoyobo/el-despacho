"""S-LC-Feedback-V6 Bloque 1A: campos `tipo` (Tarea/Entrega/Junta/Recoger) y
`hora` (opcional) en Tarea."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pizarron", "0002_tarea_ultimo_recordatorio"),
    ]

    operations = [
        migrations.AddField(
            model_name="tarea",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("tarea", "Tarea"),
                    ("entrega", "Entrega"),
                    ("junta", "Junta"),
                    ("recoger", "Recoger"),
                ],
                db_index=True,
                default="tarea",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="tarea",
            name="hora",
            field=models.TimeField(blank=True, help_text="Hora opcional del compromiso.", null=True),
        ),
    ]
