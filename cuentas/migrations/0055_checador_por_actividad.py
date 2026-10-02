"""Checador por actividad (Oscar 2026-10-01): dos interruptores por persona en El
Directorio + el umbral de una pausa larga. Sólo esquema (Bug I)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0054_seed_permiso_kpis"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="checador_por_actividad",
            field=models.BooleanField(
                default=False, verbose_name="Checador por actividad",
                help_text="La jornada se cuenta sola: de su primera a su última actividad del día "
                          "en El Taller (el día corta a las 23:59). Puede seguir checando a mano; "
                          "lo que cheque a mano gana."),
        ),
        migrations.AddField(
            model_name="usuario",
            name="checador_descontar_pausas",
            field=models.BooleanField(
                default=False, verbose_name="Descontar pausas largas",
                help_text="Con el Checador por actividad: no cuenta los huecos sin actividad más "
                          "largos que los minutos de abajo (la comida, por ejemplo)."),
        ),
        migrations.AddField(
            model_name="usuario",
            name="checador_pausa_min",
            field=models.PositiveIntegerField(
                default=60, verbose_name="Minutos de una pausa larga",
                help_text="Un hueco sin actividad más largo que esto no cuenta como trabajado."),
        ),
    ]
