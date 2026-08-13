"""Foto de los Productos involucrados por versión de cotización.

S-Ajustes-Ago12-B (Oscar 2026-08-12): las pestañas v1/v2/… del recuadro
«Productos involucrados» necesitan lo que la cotización NO guarda —merma, costo
unitario, proveedor y procesos de producción—, porque «las cotizaciones son de
salida y vista de clientes». Ver el docstring de
`apps.los_proyectos.models.producto_version`.

Aditiva: crea `proyectos_producto_version` y no toca ninguna tabla existente.
Los datos de las versiones que ya existen los reconstruye `0034`.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0032_costo_unitario_expr"),
        # Se apunta a `Cotizacion` y a `CotizacionItem`, así que sus tablas
        # deben existir en su forma actual (`agrupado` incluido).
        ("cotizaciones", "0017_item_agrupado"),
        ("el_catalogo", "0014_servicio_proveedor_principal"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProyectoProductoVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField(db_index=True, default=0)),
                ("nombre_proyecto", models.CharField(blank=True, default="", max_length=150)),
                ("cantidad", models.PositiveIntegerField(default=1)),
                ("merma", models.PositiveIntegerField(
                    default=0,
                    help_text="Piezas extra que se produjeron y no se cobraron.")),
                ("precio_unitario", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True)),
                ("costo_unitario", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True)),
                ("costo_unitario_expr", models.CharField(blank=True, default="", max_length=120)),
                ("nota", models.TextField(blank=True, default="")),
                ("imagen_file_id", models.CharField(blank=True, default="", max_length=100)),
                ("incluir_en_calculo", models.BooleanField(default=True)),
                ("procesos_json", models.JSONField(blank=True, default=list)),
                ("ventas_json", models.JSONField(blank=True, default=list)),
                ("reconstruido", models.BooleanField(default=False)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("cotizacion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="productos_version", to="cotizaciones.cotizacion")),
                ("item", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="snapshot_proyecto", to="cotizaciones.cotizacionitem")),
                ("servicio", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="en_versiones_proyecto", to="el_catalogo.servicio")),
                ("variacion", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="en_versiones_proyecto", to="el_catalogo.variacion")),
                ("proveedor", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="productos_version_proyecto", to="el_catalogo.proveedor")),
            ],
            options={
                "verbose_name": "producto de la versión",
                "verbose_name_plural": "productos de la versión",
                "db_table": "proyectos_producto_version",
                "ordering": ["orden", "pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="proyectoproductoversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("item__isnull", False)),
                fields=("cotizacion", "item"),
                name="ppv_una_foto_por_item",
            ),
        ),
    ]
