"""Agrega 'grok' (Chalán Grok, xAI) y elimina 'ollama' (Chalán Llama, Test).

Grok es cloud estándar: usa el slot `chalan_grok_api_key` y entra solo a la
cadena de fallback al guardar la llave (signal `auto_agregar_a_cadena_fallback`),
igual que MiMo/Gemini. Por eso NO se siembra fila en CadenaFallback aquí.

Ollama se retira por completo (ya no se usa). Además de quitarlo de los choices,
esta migración limpia cualquier dato residual que lo referencie para no dejar
proveedores huérfanos sin adapter:
  - CuadroChalanes con proveedor='ollama' → se reasigna a 'anthropic' (el
    primario por defecto; el adapter usa su modelo default con modelo="").
  - ChalanAsignado / CadenaFallback con proveedor='ollama' → se eliminan.
  - Credencial `chalan_ollama_base_url` → se elimina.

El catálogo de Chalanes queda con: anthropic, openai, deepseek, gemini, mimo, grok.
"""

from django.db import migrations, models

_CHOICES = [
    ("anthropic", "Chalán Claudio (Anthropic)"),
    ("openai", "Chalán GPT (OpenAI)"),
    ("deepseek", "Chalán Chino (Deepseek)"),
    ("gemini", "Chalán Gemini (Google)"),
    ("mimo", "Chalán MiMo (Xiaomi)"),
    ("grok", "Chalán Grok (xAI)"),
]


def _limpiar_ollama(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    ChalanAsignado = apps.get_model("chalanes", "ChalanAsignado")
    CadenaFallback = apps.get_model("chalanes", "CadenaFallback")
    # Reasigna estaciones que apuntaban a ollama al primario por defecto.
    CuadroChalanes.objects.filter(proveedor="ollama").update(
        proveedor="anthropic", modelo=""
    )
    ChalanAsignado.objects.filter(proveedor="ollama").delete()
    CadenaFallback.objects.filter(proveedor="ollama").delete()
    # Borra la credencial del base URL de Ollama si quedó guardada.
    try:
        Credencial = apps.get_model("ajustes", "Credencial")
        Credencial.objects.filter(clave="chalan_ollama_base_url").delete()
    except LookupError:
        pass


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0018_ollama_proveedor"),
        ("ajustes", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cuadrochalanes",
            name="proveedor",
            field=models.CharField(choices=_CHOICES, max_length=30),
        ),
        migrations.RunPython(_limpiar_ollama, _noop),
    ]
