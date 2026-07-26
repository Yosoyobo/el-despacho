"""LC 2026-07-26 (Oscar) — varias razones sociales de facturación por cliente.

Dos cambios que van juntos:

1. Tabla nueva `cartera_cliente_razon_social`: un cliente puede facturar bajo
   más de una razón social (cada una con su RFC). La `principal` se espeja a los
   campos legacy del Cliente, así que nada del código viejo cambia.
2. **Se retira la restricción de RFC único.** Una misma razón social (Grupo
   Lazanto) puede aplicar para dos clientes distintos (Cueva y Kari Kari), y la
   restricción impedía capturar ese caso real.

La data migration siembra la razón social que ya tenía cada cliente para que la
lista arranque igual a lo capturado (idempotente).
"""

import django.db.models.deletion
from django.db import migrations, models


def sembrar(apps, schema_editor):
    Cliente = apps.get_model("cartera", "Cliente")
    Razon = apps.get_model("cartera", "ClienteRazonSocial")
    for cli in Cliente.objects.exclude(razon_social_fiscal="", rfc=""):
        if Razon.objects.filter(cliente=cli).exists():
            continue
        Razon.objects.create(
            cliente=cli,
            razon_social=(cli.razon_social_fiscal or cli.razon_social or "")[:200],
            rfc=cli.rfc or "",
            principal=True,
        )


def revertir(apps, schema_editor):
    """No borra nada: los datos capturados aparte se conservan."""


class Migration(migrations.Migration):

    dependencies = [
        ("cartera", "0007_cliente_razon_social_fiscal"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="cliente",
            name="cartera_cliente_rfc_unique_nonempty",
        ),
        migrations.CreateModel(
            name="ClienteRazonSocial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("razon_social", models.CharField(
                    help_text="Nombre legal como aparece en el CFDI.", max_length=200)),
                ("rfc", models.CharField(blank=True, db_index=True, default="", max_length=13)),
                ("principal", models.BooleanField(
                    default=False, help_text="La que se usa por default al facturar.")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("cliente", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="razones_sociales", to="cartera.cliente")),
            ],
            options={
                "verbose_name": "razón social de cliente",
                "verbose_name_plural": "razones sociales de cliente",
                "db_table": "cartera_cliente_razon_social",
                "ordering": ["-principal", "razon_social"],
            },
        ),
        migrations.RunPython(sembrar, revertir),
    ]
