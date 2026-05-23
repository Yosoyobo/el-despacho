"""S-LC-Feedback-V4: FK variacion en CotizacionItem (espejo de ProyectoProducto).

Permite que cada línea de cotización referencie un servicio + variación del
catálogo (igual que el form de Proyecto). La descripción pasa a ser opcional
porque se autocompleta desde el nombre del servicio/variación.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0002_anticipo"),
        ("el_catalogo", "0005_proveedor"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacionitem",
            name="variacion",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="lineas_cotizacion",
                to="el_catalogo.variacion",
            ),
        ),
        migrations.AlterField(
            model_name="cotizacionitem",
            name="descripcion",
            field=models.TextField(blank=True, default=""),
        ),
    ]
