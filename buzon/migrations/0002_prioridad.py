"""Sprint S-LC-Feedback-V1: slider de prioridad en mensajes del Buzón.

0-10, default 5 (neutro). LC pidió poder destacar problemas urgentes
sobre sugerencias casuales sin abrir cada mensaje.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buzon", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="mensajebuzon",
            name="prioridad",
            field=models.PositiveSmallIntegerField(db_index=True, default=5),
        ),
        migrations.AlterModelOptions(
            name="mensajebuzon",
            options={
                "ordering": ["-prioridad", "-creado_en"],
                "verbose_name": "mensaje del Buzón",
                "verbose_name_plural": "mensajes del Buzón",
            },
        ),
    ]
