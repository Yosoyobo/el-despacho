"""S-LC-Buzon-V2: EstadoBuzon gana `descripcion` (significado) y `accion`
(automática al entrar al estado); MensajeBuzon gana `estado_manual` (#3: el
estado fijado a mano manda sobre el auto-avance al abrir)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("buzon", "0006_tipo_buzon"),
    ]

    operations = [
        migrations.AddField(
            model_name="estadobuzon",
            name="descripcion",
            field=models.CharField(
                blank=True, default="", max_length=200,
                help_text="Qué significa este estado (visible como ayuda al equipo).",
            ),
        ),
        migrations.AddField(
            model_name="estadobuzon",
            name="accion",
            field=models.CharField(
                default="ninguna", max_length=24,
                choices=[
                    ("ninguna", "Ninguna"),
                    ("notificar_autor", "Avisar al autor del mensaje (push)"),
                    ("notificar_admins", "Avisar a los admins del Buzón (push)"),
                ],
                help_text="Acción automática al mover un mensaje a este estado.",
            ),
        ),
        migrations.AddField(
            model_name="mensajebuzon",
            name="estado_manual",
            field=models.BooleanField(default=False),
        ),
    ]
