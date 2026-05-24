"""FK Unidad en CotizacionItem (preserva CharField legacy).

Crea `unidad_fk` ForeignKey opcional al catálogo `el_catalogo.Unidad`.
Pobla los registros existentes haciendo match case-insensitive contra
`Unidad.nombre`. Si no hay match, la fila queda con `unidad_fk = NULL`
y el CharField `unidad` original sigue siendo la fuente de verdad
(`unidad_label` lo expone).
"""

from django.db import migrations, models


def _link_existing(apps, schema_editor):
    CotizacionItem = apps.get_model("cotizaciones", "CotizacionItem")
    Unidad = apps.get_model("el_catalogo", "Unidad")
    unidades = {u.nombre.lower(): u.pk for u in Unidad.objects.all()}
    if not unidades:
        return
    for it in CotizacionItem.objects.filter(unidad_fk__isnull=True).iterator():
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
        ("cotizaciones", "0004_vencida_notificada_en"),
        ("el_catalogo", "0005_proveedor"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacionitem",
            name="unidad_fk",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=models.deletion.PROTECT,
                related_name="lineas_cotizacion",
                to="el_catalogo.unidad",
                help_text="Catálogo. Si está vacío, se usa la cadena en 'unidad' (legacy).",
            ),
        ),
        migrations.RunPython(_link_existing, _noop),
    ]
