"""Toggle de IVA por proveedor en un proyecto (reporte Oscar).

Tabla nueva `proyectos_proveedor_iva`: sin fila ⇒ IVA prendido (default). Se
persiste solo cuando el usuario cambia el toggle de un proveedor en ESTE
proyecto. Escrita a mano (makemigrations genera espurios en este repo).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0019_proceso_por_pieza"),
        ("el_catalogo", "0007_proveedor_direccion_fiscal"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProyectoProveedorIva",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("aplica_iva", models.BooleanField(default=True)),
                (
                    "proveedor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="el_catalogo.proveedor",
                    ),
                ),
                (
                    "proyecto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proveedores_iva",
                        to="proyectos.proyecto",
                    ),
                ),
            ],
            options={
                "db_table": "proyectos_proveedor_iva",
                "verbose_name": "IVA de proveedor en proyecto",
                "verbose_name_plural": "IVA de proveedores en proyecto",
                "unique_together": {("proyecto", "proveedor")},
            },
        ),
    ]
