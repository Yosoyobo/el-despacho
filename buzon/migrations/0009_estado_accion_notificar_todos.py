"""S-LC-Feedback-V11: nueva acción `notificar_todos` para estados del Buzón.

Permite que un estado (típicamente «implementado») avise por push a TODO el
equipo cuando un mensaje entra en él (decisión Oscar: "que todos sepan" las
novedades). Solo cambia `choices` — sin cambio de schema en la DB.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buzon", "0008_hilo_comentarios"),
    ]

    operations = [
        migrations.AlterField(
            model_name="estadobuzon",
            name="accion",
            field=models.CharField(
                choices=[
                    ("ninguna", "Ninguna"),
                    ("notificar_autor", "Avisar al autor del mensaje (push)"),
                    ("notificar_admins", "Avisar a los admins del Buzón (push)"),
                    ("notificar_todos", "Avisar a TODO el equipo (push) — para «implementado» / novedades"),
                ],
                default="ninguna",
                help_text="Acción automática al mover un mensaje a este estado.",
                max_length=24,
            ),
        ),
    ]
