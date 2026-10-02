"""Checador por actividad (Oscar 2026-10-01): qué extremo de la jornada puso la
actividad, primera/última actividad del día, la última ubicación y las pausas
descontadas. Sólo esquema (Bug I)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("checador", "0010_seed_permisos_nomina"),
    ]

    operations = [
        migrations.AddField(
            model_name="jornada", name="entrada_por_actividad",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="jornada", name="salida_por_actividad",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="jornada", name="actividad_primera_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="jornada", name="actividad_ultima_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="jornada", name="actividad_lat",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="jornada", name="actividad_lng",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="jornada", name="actividad_precision",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="jornada", name="pausa_min",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
