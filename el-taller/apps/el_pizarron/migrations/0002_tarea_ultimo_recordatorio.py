"""Idempotencia del cron de recordatorios (S-Chalanes-UX #4)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pizarron', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tarea',
            name='ultimo_recordatorio',
            field=models.DateField(blank=True, null=True),
        ),
    ]
