"""Procesos de VENTA de un producto del proyecto (LC 2026-07-26, Oscar).

Aditiva: crea `proyectos_producto_venta`. Los procesos de venta son lo que se le
cobra APARTE al cliente (Ponchado, arte…) y viajan a la cotización como líneas
propias. Nada que migrar de datos: hoy no existen.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0026_producto_imagen"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProyectoProductoVenta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("orden", models.PositiveSmallIntegerField(default=0)),
                ("descripcion", models.CharField(
                    help_text="Cómo se le cobra al cliente (ej. «Ponchado», «Diseño de arte»).",
                    max_length=200)),
                ("cantidad", models.PositiveIntegerField(default=1)),
                ("precio_unitario", models.DecimalField(decimal_places=2, default=0,
                                                        max_digits=12)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("producto", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ventas", to="proyectos.proyectoproducto")),
            ],
            options={
                "verbose_name": "proceso de venta del producto",
                "verbose_name_plural": "procesos de venta del producto",
                "db_table": "proyectos_producto_venta",
                "ordering": ["orden", "creado_en"],
            },
        ),
    ]
