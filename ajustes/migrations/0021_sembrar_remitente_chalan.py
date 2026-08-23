"""Deja `chalan@learningcenter.mx` como remitente de El Chalán.

Oscar, 2026-08-23: «el correo salió de hola@ y no de chalán@». El alias ya
está dado de alta en Google y sembrado por la `0018`, así que lo único que
faltaba era que algo lo eligiera.

Idempotente y conservadora: sólo escribe si el campo está vacío (no pisa una
decisión tomada desde el GUI) y sólo si ese alias existe en el registro — si
alguien lo borró, se queda en el remitente general en vez de apuntar a una
dirección que Google reescribiría en silencio.
"""

from django.db import migrations

ALIAS_CHALAN = "chalan@learningcenter.mx"


def _sembrar(apps, schema_editor):
    Config = apps.get_model("ajustes", "ConfiguracionCorreo")
    Alias = apps.get_model("ajustes", "AliasRemitente")
    if not Alias.objects.filter(email=ALIAS_CHALAN).exists():
        return
    Config.objects.filter(pk=1).filter(remitente_chalan="").update(
        remitente_chalan=ALIAS_CHALAN
    )


def _revertir(apps, schema_editor):
    Config = apps.get_model("ajustes", "ConfiguracionCorreo")
    Config.objects.filter(remitente_chalan=ALIAS_CHALAN).update(remitente_chalan="")


class Migration(migrations.Migration):

    dependencies = [
        ("ajustes", "0020_remitente_chalan"),
    ]

    operations = [
        migrations.RunPython(_sembrar, _revertir),
    ]
