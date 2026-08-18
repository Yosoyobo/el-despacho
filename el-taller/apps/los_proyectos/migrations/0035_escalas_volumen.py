"""Escalas de volumen del producto (Opción B, C…) + el ojo de la Opción A.

LC 2026-08-17 (Oscar, render `b-render-tarjeta`): un mismo producto se cotiza a
varias cantidades y el cliente escoge. Ver el docstring de
`apps.los_proyectos.models.escala`.

Aditiva: crea `proyectos_producto_escala` y agrega `visible_pdf` a
`proyectos_producto` con default True — los proyectos que ya existen quedan
exactamente como estaban (una sola opción, visible, sin escalas).

Escrita a mano: `makemigrations` cuela además el rename de un índice de
`ActividadProyecto` y los `AlterField id` de BigAutoField, que son el drift
conocido del repo (§14) y no tienen nada que ver con este sprint.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0034_backfill_producto_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyectoproducto",
            name="visible_pdf",
            field=models.BooleanField(default=True),
        ),
        # La foto por versión guarda TODO lo del lado del proyecto, así que las
        # escalas también se congelan con ella.
        migrations.AddField(
            model_name="proyectoproductoversion",
            name="visible_pdf",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="proyectoproductoversion",
            name="escalas_json",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="ProyectoProductoEscala",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("orden", models.PositiveSmallIntegerField(default=0)),
                ("cantidad", models.PositiveIntegerField(default=1)),
                ("merma", models.PositiveIntegerField(
                    default=0,
                    help_text="Piezas extra de ESTA escala. Suman costo, no se cobran.")),
                ("precio_unitario", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    help_text="Precio por unidad de esta escala. Vacío = el de la Opción A.")),
                ("costo_unitario", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    help_text="Costo por unidad de esta escala. Vacío = el de la Opción A.")),
                ("costo_unitario_expr", models.CharField(blank=True, default="", max_length=120)),
                ("impresion_costo", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    help_text="Costo de impresión de esta escala. Vacío = el de la Opción A.")),
                ("impresion_costo_expr", models.CharField(blank=True, default="", max_length=120)),
                ("impresion_por_pieza", models.BooleanField(default=False)),
                ("extras_json", models.JSONField(blank=True, default=list)),
                ("activa", models.BooleanField(
                    default=False,
                    help_text="Esta escala es la que calcula el dinero del proyecto.")),
                ("visible_pdf", models.BooleanField(
                    default=True,
                    help_text="Esta escala se imprime en la cotización.")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("producto", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="escalas", to="proyectos.proyectoproducto")),
            ],
            options={
                "verbose_name": "escala de volumen del producto",
                "verbose_name_plural": "escalas de volumen del producto",
                "db_table": "proyectos_producto_escala",
                "ordering": ["orden", "creado_en"],
            },
        ),
        migrations.AddConstraint(
            model_name="proyectoproductoescala",
            constraint=models.UniqueConstraint(
                condition=models.Q(("activa", True)),
                fields=("producto",),
                name="escala_activa_unica_por_producto",
            ),
        ),
    ]
