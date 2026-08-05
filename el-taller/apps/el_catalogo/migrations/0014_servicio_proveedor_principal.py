"""LC 2026-08-04 R3 (Oscar) — el proveedor PRINCIPAL del producto, explícito.

El proveedor que se le pone a un producto dentro de un proyecto ahora se liga al
catálogo (entra a `Servicio.proveedores`). Para que eso no le robe el default al
proveedor de siempre, el principal deja de ser «el primero de la M2M» —que en
realidad era el primero ALFABÉTICO— y pasa a ser este FK explícito.

La data migration lo siembra con el que hoy se está usando (el primer activo por
razón social), así que nada cambia de comportamiento al aplicarla.
"""

import django.db.models.deletion
from django.db import migrations, models


def sembrar_principal(apps, schema_editor):
    Servicio = apps.get_model("el_catalogo", "Servicio")
    for srv in Servicio.objects.prefetch_related("proveedores").filter(
        proveedor_principal__isnull=True
    ):
        prov = next(
            (p for p in srv.proveedores.all() if p.activo),
            None,
        )
        if prov is not None:
            srv.proveedor_principal_id = prov.pk
            srv.save(update_fields=["proveedor_principal"])


def revertir(apps, schema_editor):
    """No-op: el FK se va con el RemoveField del rollback."""


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0013_servicio_procesos_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicio",
            name="proveedor_principal",
            field=models.ForeignKey(
                blank=True,
                help_text="El que surte este producto por default. Los demás quedan como alternativas.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="productos_principales",
                to="el_catalogo.proveedor",
            ),
        ),
        migrations.RunPython(sembrar_principal, revertir),
    ]
