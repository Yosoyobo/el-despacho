"""Suelta los mandados de tareas que dejaron de ser entrega/recoger (Buzón #155/#165).

Sólo `RunPython`, sin cambios de esquema. Misma regla que
`mandados.soltar_mandado_sobrante`: el que no salió se borra, el que iba en
camino se cancela y el entregado se queda como historia.
"""

from django.db import migrations
from django.utils import timezone

TIPOS_RUNNER = ("entrega", "recoger")


def _soltar(apps, schema_editor):
    Mandado = apps.get_model("pizarron", "Mandado")
    sobrantes = Mandado.objects.exclude(tarea__tipo__in=TIPOS_RUNNER)
    sobrantes.filter(estado__in=("por_asignar", "asignado", "cancelado")).delete()
    sobrantes.filter(estado="en_camino").update(estado="cancelado", cancelado_en=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("pizarron", "0016_tarea_producto"),
    ]

    operations = [
        migrations.RunPython(_soltar, migrations.RunPython.noop),
    ]
