"""S-LC-Buzon: contactos múltiples por cliente. Crea ClienteContacto y siembra
uno (principal) por cada cliente con datos de contacto legacy.
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill(apps, schema_editor):
    Cliente = apps.get_model("cartera", "Cliente")
    ClienteContacto = apps.get_model("cartera", "ClienteContacto")
    for c in Cliente.objects.all():
        if c.nombre_contacto or c.email_contacto or c.telefono:
            ClienteContacto.objects.get_or_create(
                cliente=c,
                nombre=c.nombre_contacto or "Contacto",
                defaults={
                    "email": c.email_contacto or "",
                    "telefono": c.telefono or "",
                    "principal": True,
                },
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("cartera", "0002_cliente_slug"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClienteContacto",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=200)),
                ("puesto", models.CharField(blank=True, default="", max_length=120)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("telefono", models.CharField(blank=True, default="", max_length=40)),
                ("principal", models.BooleanField(default=False)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("cliente", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contactos", to="cartera.cliente")),
            ],
            options={
                "db_table": "cartera_cliente_contacto",
                "verbose_name": "contacto de cliente",
                "verbose_name_plural": "contactos de cliente",
                "ordering": ["-principal", "nombre"],
            },
        ),
        migrations.RunPython(backfill, noop),
    ]
