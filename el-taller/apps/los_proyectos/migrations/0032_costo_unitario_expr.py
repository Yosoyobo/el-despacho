"""El costo unitario de una línea se puede escribir como una cuenta.

LC 2026-08-12 (Oscar): «en la tarjeta de producto involucrado, el campo de
costo unitario en proveedor principal (o secundario) habilitemos que también se
pueda escribir y calcular, por ejemplo 15.75*100».

Aditiva: `costo_unitario` sigue guardando el total; este campo conserva la
cuenta tal como se escribió, igual que el `costo_expr` de la impresión.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0031_motivo_cancelacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyectoproducto",
            name="costo_unitario_expr",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
    ]
