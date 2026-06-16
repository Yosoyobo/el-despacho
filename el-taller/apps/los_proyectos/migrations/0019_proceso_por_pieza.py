from django.db import migrations, models


def _impresion_por_pieza(apps, schema_editor):
    """S-LC-Proyecto-V2 (Oscar): la impresión existente pasa a 'por pieza'
    (era fija y se contaba una sola vez). Los operativos quedan fijos."""
    Proceso = apps.get_model("proyectos", "ProyectoProductoProceso")
    Proceso.objects.filter(tipo="impresion").update(por_pieza=True)


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0018_estado_descripcion_accion"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyectoproductoproceso",
            name="por_pieza",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(_impresion_por_pieza, _noop),
    ]
