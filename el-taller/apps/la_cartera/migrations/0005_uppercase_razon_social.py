from django.db import migrations


def uppercase_razon_social(apps, schema_editor):
    """Fuerza MAYÚSCULAS en el nombre (razón social) de TODOS los clientes
    existentes. str.upper() respeta acentos en español ("josé" → "JOSÉ").
    Idempotente: sólo guarda los que difieren."""
    Cliente = apps.get_model("cartera", "Cliente")
    for c in Cliente.objects.all().iterator():
        nuevo = (c.razon_social or "").upper()
        if c.razon_social != nuevo:
            c.razon_social = nuevo
            c.save(update_fields=["razon_social"])


class Migration(migrations.Migration):

    dependencies = [
        ("cartera", "0004_cliente_direccion_fiscal"),
    ]

    operations = [
        migrations.RunPython(uppercase_razon_social, migrations.RunPython.noop),
    ]
