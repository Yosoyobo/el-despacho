import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pizarron", "0006_estado_descripcion_accion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="tarea",
            name="runner",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tareas_para_repartir",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="tarea",
            name="requiere_runner",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="tarea",
            name="runner_auto",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="tarea",
            name="runner_asignado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
