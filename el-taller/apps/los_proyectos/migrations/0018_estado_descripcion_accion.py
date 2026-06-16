"""S-LC-Feedback-V12: EstadoProyecto gana `descripcion` y `accion` para igualar
el layout de los estados del Buzón en La Gerencia (pedido de Oscar). La acción
es DOCUMENTAL por ahora — no dispara push todavía. Una data migration siembra
descripciones razonables para los estados sistema (idempotente: solo si están
vacías)."""

from django.db import migrations, models

ACCIONES = [
    ("ninguna", "Ninguna"),
    ("notificar_equipo", "Avisar al equipo del proyecto (push)"),
    ("notificar_lider", "Avisar al líder / responsable (push)"),
    ("notificar_todos", "Avisar a TODO el equipo (push)"),
]

DESCRIPCIONES = {
    "por_cotizar": "Aún no se cotiza. Pendiente de armar la propuesta.",
    "esperando_respuesta": "Cotización enviada; esperando que el cliente apruebe.",
    "en_proceso_diseno": "El equipo está diseñando.",
    "en_proceso_produccion": "En producción / maquila.",
    "entregado": "Entregado al cliente.",
    "cerrado": "Proyecto cerrado.",
    "en_pausa": "Detenido temporalmente.",
    "cancelado": "Cancelado; no continúa.",
}


def sembrar_descripciones(apps, schema_editor):
    Estado = apps.get_model("proyectos", "EstadoProyecto")
    for slug, texto in DESCRIPCIONES.items():
        Estado.objects.filter(slug=slug, descripcion="").update(descripcion=texto)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("proyectos", "0017_proceso_egreso"),
    ]

    operations = [
        migrations.AddField(
            model_name="estadoproyecto",
            name="descripcion",
            field=models.CharField(
                blank=True, default="", max_length=200,
                help_text="Qué significa este estado (visible como ayuda al equipo).",
            ),
        ),
        migrations.AddField(
            model_name="estadoproyecto",
            name="accion",
            field=models.CharField(
                default="ninguna", max_length=24, choices=ACCIONES,
                help_text="Acción prevista al mover un proyecto a este estado "
                          "(documental por ahora; el push automático llega después).",
            ),
        ),
        migrations.RunPython(sembrar_descripciones, noop),
    ]
