# C6 S-LC-Feedback-V6 — Inicio y Entrega del proyecto pasan a fecha+hora.
# Las fechas existentes se conservan poniéndoles las 12:00 PM (hora local).

from django.db import migrations, models


def _poner_mediodia(apps, schema_editor):
    """Pone las fechas existentes a las 12:00 PM local.

    Tras el AlterField (DateField → DateTimeField) las fechas previas quedan a
    las 00:00. LC pidió default 12:00, así que las normalizamos a mediodía.
    """
    from datetime import datetime, time

    from django.utils import timezone

    Proyecto = apps.get_model("proyectos", "Proyecto")
    tz = timezone.get_default_timezone()
    for p in Proyecto.objects.exclude(fecha_inicio=None) | Proyecto.objects.exclude(fecha_compromiso=None):
        cambia = False
        for campo in ("fecha_inicio", "fecha_compromiso"):
            valor = getattr(p, campo)
            if valor is None:
                continue
            local = timezone.localtime(valor, tz) if timezone.is_aware(valor) else valor
            mediodia = datetime.combine(local.date(), time(12, 0))
            if timezone.is_naive(mediodia):
                mediodia = timezone.make_aware(mediodia, tz)
            setattr(p, campo, mediodia)
            cambia = True
        if cambia:
            p.save(update_fields=["fecha_inicio", "fecha_compromiso"])


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0007_estado_proyecto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proyecto',
            name='fecha_compromiso',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='proyecto',
            name='fecha_inicio',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(_poner_mediodia, migrations.RunPython.noop),
    ]
