"""FK Unidad en FacturaItem (espejo de la migración análoga en Cotizaciones)."""

from django.db import migrations, models


def _link_existing(apps, schema_editor):
    FacturaItem = apps.get_model("facturacion", "FacturaItem")
    Unidad = apps.get_model("el_catalogo", "Unidad")
    unidades = {u.nombre.lower(): u.pk for u in Unidad.objects.all()}
    if not unidades:
        return
    for it in FacturaItem.objects.filter(unidad_fk__isnull=True).iterator():
        nombre = (it.unidad or "").strip().lower()
        if not nombre:
            continue
        pk = unidades.get(nombre)
        if pk:
            it.unidad_fk_id = pk
            it.save(update_fields=["unidad_fk"])


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion", "0002_vencida_notificada_en"),
        ("el_catalogo", "0005_proveedor"),
    ]

    operations = [
        migrations.AddField(
            model_name="facturaitem",
            name="unidad_fk",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=models.deletion.PROTECT,
                related_name="lineas_factura",
                to="el_catalogo.unidad",
                help_text="Catálogo. Si está vacío, se usa la cadena en 'unidad' (legacy).",
            ),
        ),
        migrations.RunPython(_link_existing, _noop),
    ]
