"""S-Estados-Color-HEX: el color del estado pasa de clases badge-* a HEX libre.

AlterField (quita choices, max_length 7, default hex) + data migration que
convierte los valores badge-* existentes a su HEX de la paleta TailAdmin.
Idempotente: filas que ya tengan un hex (#...) se dejan intactas; cualquier
valor desconocido cae al gris neutro.
"""

from __future__ import annotations

import django.core.validators
from django.db import migrations, models

BADGE_A_HEX = {
    "badge-blue": "#0ba5ec",
    "badge-orange": "#fb6514",
    "badge-warning": "#f79009",
    "badge-success": "#12b76a",
    "badge-error": "#f04438",
    "badge-gray": "#667085",
    "badge-brand": "#465fff",
    "badge-purple": "#7a5af8",
}


def badge_a_hex(apps, schema_editor):
    EstadoProyecto = apps.get_model("proyectos", "EstadoProyecto")
    for e in EstadoProyecto.objects.all():
        valor = (e.color or "").strip()
        if valor.startswith("#"):
            continue
        e.color = BADGE_A_HEX.get(valor, "#667085")
        e.save(update_fields=["color"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("proyectos", "0013_estado_cerrado")]

    operations = [
        migrations.AlterField(
            model_name="estadoproyecto",
            name="color",
            field=models.CharField(
                default="#667085",
                help_text="Color HEX del badge, ej. #465fff.",
                max_length=7,
                validators=[django.core.validators.RegexValidator(
                    message="Usa un color hexadecimal de 6 dígitos, ej. #465fff.",
                    regex=r"^#[0-9a-fA-F]{6}$",
                )],
            ),
        ),
        migrations.RunPython(badge_a_hex, noop),
    ]
