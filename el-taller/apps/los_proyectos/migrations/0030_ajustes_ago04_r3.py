"""LC 2026-08-04 R3 (Oscar) — tres cambios de la ronda:

* `ProyectoProductoProceso.costo_expr`: la CUENTA escrita en el costo de la
  impresión («35+15+15»). El total sigue en `costo`.
* `Proyecto.orden_kanban`: orden manual de las tarjetas del Kanban (compartido).
* `ProyectoProducto.Meta.ordering` deja de mandar las incluidas al tope, para que
  prender/apagar un toggle no reacomode las tarjetas.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0029_descripcion_desde_cotizaciones"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyectoproductoproceso",
            name="costo_expr",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="orden_kanban",
            field=models.IntegerField(db_index=True, default=0),
        ),
        migrations.AlterModelOptions(
            name="proyectoproducto",
            options={
                "ordering": ["orden", "creado_en"],
                "verbose_name": "producto del proyecto",
                "verbose_name_plural": "productos del proyecto",
            },
        ),
    ]
