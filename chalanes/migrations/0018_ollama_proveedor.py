"""Agrega 'ollama' (Chalán Llama, Test) como proveedor en CuadroChalanes.

Sólo actualiza los choices del campo (no toca datos). El catálogo de Chalanes
queda con: anthropic, openai, deepseek, gemini, mimo, ollama.

NO siembra fila en CadenaFallback: el Chalán Llama es un servidor local de
pruebas (Ollama vía Tailscale) que NO debe entrar solo al fallback de
producción. El super_admin lo asigna a una estación a mano desde /chalanes/.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0017_analisis_negocio_estacion"),
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
                    ("ollama", "Chalán Llama (Test)"),
                ],
                max_length=30,
            ),
        ),
    ]
