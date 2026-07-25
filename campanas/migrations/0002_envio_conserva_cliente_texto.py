"""El registro de envío de campaña sobrevive al borrado del cliente.

LC 2026-07-25 (Oscar): «borrar al cliente, si hay registros de envíos de campaña
conservar los registros (mencionando al cliente solo como texto)».

Antes `CampanaEnvio.cliente` era `PROTECT`, así que un cliente que hubiera
recibido UNA campaña quedaba imposible de eliminar — y no hay pantalla para
tocar esos registros. Ahora es `SET_NULL` + `cliente_nombre` (snapshot del
nombre al momento del envío), que se rellena hacia atrás desde el FK.
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_nombre(apps, schema_editor):
    CampanaEnvio = apps.get_model("campanas", "CampanaEnvio")
    for envio in CampanaEnvio.objects.filter(cliente_nombre="").select_related("cliente"):
        if envio.cliente_id:
            CampanaEnvio.objects.filter(pk=envio.pk).update(
                cliente_nombre=envio.cliente.razon_social[:200]
            )


class Migration(migrations.Migration):

    dependencies = [
        ("campanas", "0001_initial"),
        ("cartera", "0007_cliente_razon_social_fiscal"),
    ]

    operations = [
        migrations.AddField(
            model_name="campanaenvio",
            name="cliente_nombre",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AlterField(
            model_name="campanaenvio",
            name="cliente",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="envios_campana", to="cartera.cliente",
            ),
        ),
        migrations.RunPython(backfill_nombre, migrations.RunPython.noop),
    ]
