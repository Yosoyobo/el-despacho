"""Campo `origen` en DictadoAprendizaje (S-Chalan-Aprende-V1).

Distingue los aprendizajes enseñados a mano (`manual`) de los que el Chalán
destiló de su propio historial (`chalan_destilado`). Estos últimos nacen
inactivos y se revisan en La Gerencia antes de entrar al prompt.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_dictado", "0005_propuesta_chalan"),
    ]

    operations = [
        migrations.AddField(
            model_name="dictadoaprendizaje",
            name="origen",
            field=models.CharField(
                max_length=20,
                default="manual",
                choices=[
                    ("manual", "Enseñado a mano"),
                    ("chalan_destilado", "Destilado por el Chalán"),
                ],
            ),
        ),
    ]
