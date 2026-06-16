"""Mandado (companion 1:1 de Tarea) + backfill de entregas/recolecciones."""

import django.db.models.deletion
from django.db import migrations, models


def backfill_mandados(apps, schema_editor):
    from django.utils import timezone
    Tarea = apps.get_model("pizarron", "Tarea")
    Mandado = apps.get_model("pizarron", "Mandado")
    EstadoTarea = apps.get_model("pizarron", "EstadoTarea")

    terminales = set(
        EstadoTarea.objects.filter(terminal=True).values_list("slug", flat=True)
    ) or {"completada"}

    ahora = timezone.now()
    existentes = set(Mandado.objects.values_list("tarea_id", flat=True))
    nuevos = []
    for t in Tarea.objects.filter(tipo__in=("entrega", "recoger")):
        if t.id in existentes:
            continue
        if t.estado in terminales:
            estado = "entregado"
            nuevos.append(Mandado(
                tarea_id=t.id, estado=estado,
                asignado_en=t.runner_asignado_en,
                entregado_en=t.completada_en or ahora,
            ))
        elif t.runner_id:
            nuevos.append(Mandado(
                tarea_id=t.id, estado="asignado", asignado_en=t.runner_asignado_en or ahora,
            ))
        else:
            nuevos.append(Mandado(tarea_id=t.id, estado="por_asignar"))
    if nuevos:
        Mandado.objects.bulk_create(nuevos)


class Migration(migrations.Migration):

    dependencies = [
        ("pizarron", "0008_tarea_destino"),
    ]

    operations = [
        migrations.CreateModel(
            name="Mandado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("estado", models.CharField(
                    choices=[
                        ("por_asignar", "Por asignar"), ("asignado", "Asignado"),
                        ("en_camino", "En camino"), ("entregado", "Entregado"),
                        ("cancelado", "Cancelado"),
                    ],
                    db_index=True, default="por_asignar", max_length=16,
                )),
                ("asignado_en", models.DateTimeField(blank=True, null=True)),
                ("en_camino_en", models.DateTimeField(blank=True, null=True)),
                ("entregado_en", models.DateTimeField(blank=True, null=True)),
                ("cancelado_en", models.DateTimeField(blank=True, null=True)),
                ("notas", models.TextField(blank=True, default="")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("tarea", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="mandado", to="pizarron.tarea",
                )),
            ],
            options={
                "verbose_name": "mandado",
                "verbose_name_plural": "mandados",
                "db_table": "pizarron_mandado",
                "ordering": ["estado", "-creado_en"],
            },
        ),
        migrations.RunPython(backfill_mandados, migrations.RunPython.noop),
    ]
