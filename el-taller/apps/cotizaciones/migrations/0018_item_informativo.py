"""Renglones informativos: las alternativas de volumen del producto.

LC 2026-08-17 (Oscar): con escalas de volumen, el documento imprime «70 pz a
195», «100 a 175» y «200 a 160» dentro de la tabla de montos del producto, pero
el total sigue siendo el de la opción ACTIVA. `calcular_totales` suma TODAS las
líneas, así que sin esta bandera imprimir las alternativas duplicaría el total.

Aditiva, default False: los documentos que ya existen no cambian ni un centavo.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0017_item_agrupado"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacionitem",
            name="informativo",
            field=models.BooleanField(
                default=False,
                help_text="Alternativa de volumen: se imprime pero no suma al total.",
            ),
        ),
    ]
