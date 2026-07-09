from django.db import migrations, models


def _set_regimen(apps, schema_editor):
    """Deriva el régimen fiscal de los proyectos existentes: los exentos quedan
    'exento', el resto 'iva' (comportamiento previo, IVA 16%)."""
    Proyecto = apps.get_model("proyectos", "Proyecto")
    Proyecto.objects.filter(iva_exento=True).update(regimen_fiscal="exento")
    Proyecto.objects.filter(iva_exento=False).update(regimen_fiscal="iva")


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0021_proyecto_archivado"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyecto",
            name="regimen_fiscal",
            field=models.CharField(
                choices=[
                    ("iva", "IVA (16%)"),
                    ("honorarios", "IVA y Retenciones"),
                    ("exento", "Exento"),
                ],
                default="iva",
                db_index=True,
                max_length=12,
            ),
        ),
        migrations.RunPython(_set_regimen, _noop),
    ]
