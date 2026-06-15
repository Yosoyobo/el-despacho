"""S-LC-Feedback-V10 — aviso del momento de cumplimiento (fecha+hora) por tarea."""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pizarron", "0004_estado_tarea")]
    operations = [
        migrations.AddField(
            model_name="tarea",
            name="aviso_cumplido_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
