"""Siembra los 12 alias que Learning Center ya tiene dados de alta en Google.

Separada de la `0017` (que agrega la columna `usuario`) porque Postgres no deja
crear el índice de una llave foránea en la misma transacción en la que se
insertaron filas — ver el detalle en el encabezado de la `0017`.

# Los alias que Learning Center ya tiene dados de alta en Google («Enviar como»),
# tal como se ven en la cuenta hola@learningcenter.mx el 2026-08-22. Se siembran
# ya VERIFICADOS: no hace falta que nadie los compruebe otra vez, porque quien
# los creó confirmó el correo de Google al darlos de alta.
#
# `personal=True` = alias a nombre de una persona. Se siembra SIN dueño a
# propósito: ligarlo a la cuenta correcta es una decisión de alguien, y mientras
# no tenga dueño **nadie** puede mandar desde él (`puede_usarlo` lo niega). Es el
# lado seguro: un alias personal suelto no debe poder usarlo cualquiera.
"""

from django.db import migrations

ALIAS_LC = [
    ("hola@learningcenter.mx", "LEARNING CENTER", False),
    ("admin@learningcenter.mx", "ADMIN | LEARNING CENTER", False),
    ("cobranza@learningcenter.mx", "COBRANZA | LEARNING CENTER", False),
    ("facturas@learningcenter.mx", "FACTURAS | LEARNING CENTER", False),
    ("legal@learningcenter.mx", "LEGAL | LEARNING CENTER", False),
    ("pagos@learningcenter.mx", "PAGOS | LEARNING CENTER", False),
    ("runner@learningcenter.mx", "RUNNER | LEARNING CENTER", False),
    ("soporte@learningcenter.mx", "SOPORTE | LEARNING CENTER", False),
    ("ventas@learningcenter.mx", "VENTAS | LEARNING CENTER", False),
    ("chalan@learningcenter.mx", "Chalán", False),
    ("alex@learningcenter.mx", "Alexandro", True),
    ("jorge@learningcenter.mx", "Jorge", True),
]


def _sembrar(apps, schema_editor):
    """Idempotente: no pisa un alias que alguien ya haya tocado a mano."""
    from django.utils import timezone

    Alias = apps.get_model("ajustes", "AliasRemitente")
    ahora = timezone.now()
    for email, nombre, _personal in ALIAS_LC:
        Alias.objects.get_or_create(email=email, defaults={
            "nombre": nombre, "verificado": True, "verificado_en": ahora,
            "notas": "Dado de alta en Google antes de este sprint.",
        })


def _borrar_seed(apps, schema_editor):
    Alias = apps.get_model("ajustes", "AliasRemitente")
    Alias.objects.filter(email__in=[e for e, _n, _p in ALIAS_LC]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ajustes', '0017_alias_personales'),
    ]

    operations = [
        migrations.RunPython(_sembrar, _borrar_seed),
    ]
