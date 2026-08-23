"""Dónde empieza y dónde termina cada mandado, y cuánto se recorrió.

Oscar (2026-08-22): «los runners deberán checar el momento en el que empiezan la
misión y la terminan, con esto calculamos tiempos, distancia, etc.». El reloj ya
existía; esto agrega el lugar, que es lo que faltaba para medir distancia — y la
base del módulo de planeación de ruta que viene después.

Escrita a mano: makemigrations agrega AlterField espurios de BigAutoField (§14).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pizarron", "0013_tarea_orden"),
    ]

    operations = [
        migrations.AddField(
            model_name="mandado", name="inicio_lat",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="mandado", name="inicio_lng",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="mandado", name="fin_lat",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="mandado", name="fin_lng",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="mandado", name="distancia_m",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text="Línea recta entre el punto de salida y el de entrega.",
            ),
        ),
    ]
