"""Siembra la estación `ocr_recibo` en CuadroChalanes (S-Chalán-Scope-OCR).

El OCR de recibos usa `analizar(estacion="ocr_recibo", imagenes=[...])`. La
estación requiere visión; el Reemplazo filtra la cadena a los Chalanes que la
soportan (Anthropic, OpenAI, Gemini, MiMo). Sembramos el primario por default
(decisión: cadena con fallback — el super_admin reordena desde /chalanes/).

Idempotente: solo crea si no existe (no pisa lo que el super_admin haya
ajustado).
"""

from django.db import migrations

ESTACION = "ocr_recibo"
PROVEEDOR = "openai"
MODELO = "gpt-4o-mini"
DESC = "Extrae monto, fecha, proveedor y concepto de la foto de un recibo."


def seed(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    if CuadroChalanes.objects.filter(estacion=ESTACION).exists():
        return
    CuadroChalanes.objects.create(
        estacion=ESTACION,
        proveedor=PROVEEDOR,
        modelo=MODELO,
        descripcion=DESC,
        requiere_vision=True,
    )


def unseed(apps, schema_editor):
    apps.get_model("chalanes", "CuadroChalanes").objects.filter(estacion=ESTACION).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0005_taller_chat_estacion"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
