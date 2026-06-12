"""Seed del horario global default: Lunes a Viernes 9:00–18:00, tolerancia 15.

Idempotente vía update_or_create con usuario NULL (global). El super_admin
ajusta estos valores y agrega overrides por usuario desde La Gerencia (E5).
"""

from __future__ import annotations

import datetime

from django.db import migrations

HORA_ENTRADA = datetime.time(9, 0)
HORA_SALIDA = datetime.time(18, 0)
TOLERANCIA = 15
DIAS_LABORALES = (0, 1, 2, 3, 4)  # lunes..viernes (date.weekday())


def seed(apps, schema_editor):
    HorarioLaboral = apps.get_model("checador", "HorarioLaboral")
    for dia in DIAS_LABORALES:
        HorarioLaboral.objects.update_or_create(
            usuario=None,
            dia_semana=dia,
            defaults={
                "hora_entrada": HORA_ENTRADA,
                "hora_salida": HORA_SALIDA,
                "tolerancia_min": TOLERANCIA,
                "activo": True,
            },
        )


def reverse(apps, schema_editor):
    HorarioLaboral = apps.get_model("checador", "HorarioLaboral")
    HorarioLaboral.objects.filter(usuario__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("checador", "0001_initial")]
    operations = [migrations.RunPython(seed, reverse)]
