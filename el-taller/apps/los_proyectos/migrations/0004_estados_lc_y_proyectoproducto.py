"""Sprint S-LC-Feedback-V1: renombrar choices de estado para reflejar el
ciclo real del despacho LC + nuevo modelo ProyectoProducto.

Mapeo de valores viejos → nuevos:
  prospecto        → por_cotizar
  cotizado         → esperando_respuesta
  revision_cliente → esperando_respuesta
  en_diseno        → en_proceso_diseno
  en_produccion    → en_proceso_produccion
  entregado, en_pausa, cancelado se quedan.
"""

from django.db import migrations, models

MAPEO = {
    "prospecto": "por_cotizar",
    "cotizado": "esperando_respuesta",
    "revision_cliente": "esperando_respuesta",
    "en_diseno": "en_proceso_diseno",
    "en_produccion": "en_proceso_produccion",
}


def renombrar_estados(apps, schema_editor):
    Proyecto = apps.get_model("proyectos", "Proyecto")
    for viejo, nuevo in MAPEO.items():
        Proyecto.objects.filter(estado=viejo).update(estado=nuevo)


def revertir_estados(apps, schema_editor):
    Proyecto = apps.get_model("proyectos", "Proyecto")
    # Reverso: nuevo → viejo más probable.
    reverso = {
        "por_cotizar": "prospecto",
        "esperando_respuesta": "cotizado",
        "en_proceso_diseno": "en_diseno",
        "en_proceso_produccion": "en_produccion",
    }
    for nuevo, viejo in reverso.items():
        Proyecto.objects.filter(estado=nuevo).update(estado=viejo)


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0003_proyecto_slug"),
        ("el_catalogo", "0002_variacion_seed_categorias"),
    ]

    operations = [
        migrations.RunPython(renombrar_estados, revertir_estados),
        migrations.AlterField(
            model_name="proyecto",
            name="estado",
            field=models.CharField(
                choices=[
                    ("por_cotizar", "Por cotizar"),
                    ("esperando_respuesta", "Esperando respuesta"),
                    ("en_proceso_diseno", "En proceso de diseño"),
                    ("en_proceso_produccion", "En proceso de producción"),
                    ("entregado", "Entregado"),
                    ("en_pausa", "En pausa"),
                    ("cancelado", "Cancelado"),
                ],
                db_index=True,
                default="por_cotizar",
                max_length=24,
            ),
        ),
        migrations.CreateModel(
            name="ProyectoProducto",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("cantidad", models.PositiveIntegerField(default=1)),
                ("nota", models.CharField(blank=True, default="", max_length=200)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "proyecto",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="productos",
                        to="proyectos.proyecto",
                    ),
                ),
                (
                    "servicio",
                    models.ForeignKey(
                        on_delete=models.deletion.PROTECT,
                        related_name="en_proyectos",
                        to="el_catalogo.servicio",
                    ),
                ),
                (
                    "variacion",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.PROTECT,
                        related_name="en_proyectos",
                        to="el_catalogo.variacion",
                    ),
                ),
            ],
            options={
                "db_table": "proyectos_producto",
                "ordering": ["creado_en"],
                "verbose_name": "producto del proyecto",
                "verbose_name_plural": "productos del proyecto",
            },
        ),
    ]
