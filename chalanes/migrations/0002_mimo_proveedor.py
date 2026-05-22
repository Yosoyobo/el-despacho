"""Agrega 'mimo' como proveedor disponible en CuadroChalanes.

Sólo actualiza los choices del campo (no toca datos). El catálogo de cocineros
queda con: anthropic, openai, deepseek, gemini, mimo.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cuadrochalanes",
            name="proveedor",
            field=models.CharField(
                choices=[
                    ("anthropic", "Chalán Claudio (Anthropic)"),
                    ("openai", "Chalán GPT (OpenAI)"),
                    ("deepseek", "Chalán Chino (Deepseek)"),
                    ("gemini", "Chalán Gemini (Google)"),
                    ("mimo", "Chalán MiMo (Xiaomi)"),
                ],
                max_length=30,
            ),
        ),
    ]
