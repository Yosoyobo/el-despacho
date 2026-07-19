from django.db import migrations, models


class Migration(migrations.Migration):
    """LC Fase 2: orden manual (drag & drop) de las tarjetas de producto en el
    detalle del proyecto + reordena el `ordering` para que las incluidas queden
    arriba."""

    dependencies = [
        ("proyectos", "0022_regimen_fiscal"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyectoproducto",
            name="orden",
            field=models.PositiveIntegerField(default=0, db_index=True),
        ),
        migrations.AlterModelOptions(
            name="proyectoproducto",
            options={
                "ordering": ["-incluir_en_calculo", "orden", "creado_en"],
                "verbose_name": "producto del proyecto",
                "verbose_name_plural": "productos del proyecto",
            },
        ),
    ]
