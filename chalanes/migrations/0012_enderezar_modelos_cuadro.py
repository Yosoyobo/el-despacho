"""Endereza el cross-wiring proveedor↔modelo en CuadroChalanes.

Bug: el campo `modelo` era texto libre y al cambiar el Chalán de una estación
el modelo viejo se quedaba pegado (ej. Deepseek + claude-haiku-4-5), provocando
400 "The supported API model ..." y fallbacks raros.

Esta migración recorre las filas y, si el modelo NO corresponde a la familia del
proveedor (por prefijo), lo resetea al MODELO_DEFAULT de ese proveedor.
Idempotente y conservadora: solo toca filas con mismatch evidente.
"""

from __future__ import annotations

from django.db import migrations

DEFAULTS = {
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-2.5-flash",
    "mimo": "mimo-v2.5-pro",
}
PREFIJOS = {
    "anthropic": ("claude",),
    "openai": ("gpt", "o1", "o3", "o4", "chatgpt"),
    "deepseek": ("deepseek",),
    "gemini": ("gemini",),
    "mimo": ("mimo",),
}


def enderezar(apps, schema_editor):
    Cuadro = apps.get_model("chalanes", "CuadroChalanes")
    for fila in Cuadro.objects.all():
        prov = fila.proveedor
        prefijos = PREFIJOS.get(prov)
        if not prefijos:
            continue
        modelo = (fila.modelo or "").strip()
        if not modelo or not modelo.startswith(prefijos):
            nuevo = DEFAULTS.get(prov, modelo)
            if nuevo != fila.modelo:
                fila.modelo = nuevo
                fila.save(update_fields=["modelo"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("chalanes", "0011_estaciones_s4")]
    operations = [migrations.RunPython(enderezar, noop)]
