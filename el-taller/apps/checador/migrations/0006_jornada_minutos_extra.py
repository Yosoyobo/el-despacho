"""S-LC-Feedback-V11 — segmentos extra del mismo día (Checador).

Permite checar salida y volver a entrar el mismo día acumulando horas extra
sin contar la pausa (decisión Oscar: "si hago más horas de trabajo cuéntalas").
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("checador", "0005_jornada_ajustado_en_jornada_ajustado_por_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="jornada",
            name="minutos_extra",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
