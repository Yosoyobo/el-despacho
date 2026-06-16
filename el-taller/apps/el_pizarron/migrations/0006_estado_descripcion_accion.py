"""S-LC-Feedback-V12: EstadoTarea gana `descripcion` y `accion` para igualar el
layout de los estados del Buzón en La Gerencia. Acción DOCUMENTAL por ahora
(no dispara push). Data migration siembra descripciones de los estados sistema
(idempotente: solo si están vacías)."""

from django.db import migrations, models

ACCIONES = [
    ("ninguna", "Ninguna"),
    ("notificar_asignado", "Avisar a la persona asignada (push)"),
    ("notificar_todos", "Avisar a TODO el equipo (push)"),
]

DESCRIPCIONES = {
    "pendiente": "Por hacer; nadie la ha empezado.",
    "en_curso": "Alguien la está trabajando.",
    "completada": "Terminada.",
}


def sembrar_descripciones(apps, schema_editor):
    Estado = apps.get_model("pizarron", "EstadoTarea")
    for slug, texto in DESCRIPCIONES.items():
        Estado.objects.filter(slug=slug, descripcion="").update(descripcion=texto)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("pizarron", "0005_tarea_aviso_cumplido"),
    ]

    operations = [
        migrations.AddField(
            model_name="estadotarea",
            name="descripcion",
            field=models.CharField(
                blank=True, default="", max_length=200,
                help_text="Qué significa este estado (visible como ayuda al equipo).",
            ),
        ),
        migrations.AddField(
            model_name="estadotarea",
            name="accion",
            field=models.CharField(
                default="ninguna", max_length=24, choices=ACCIONES,
                help_text="Acción prevista al mover una tarea a este estado "
                          "(documental por ahora; el push automático llega después).",
            ),
        ),
        migrations.RunPython(sembrar_descripciones, noop),
    ]
