from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pizarron", "0010_evento"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="tarea",
            name="responsables",
            field=models.ManyToManyField(
                blank=True,
                related_name="tareas_corresponsable",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
