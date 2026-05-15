"""Hotfix SSO Google: agrandar campos que truenan al guardar perfiles reales.

Bug en producción: callback de Google retornaba 500 con
StringDataRightTruncation al persistir el Usuario. Diagnóstico:
- `avatar_url` (URLField default Django = 200) saturado por URLs de Google
  Workspace que incluyen tokens largos (`lh3.googleusercontent.com/a/ACg8oc...`).
- `google_sub` también queda subido por seguridad — Google documenta hasta 255
  chars; los 50 originales son un riesgo latente para cuentas Workspace.

Solo `AlterField`. Cero `RunPython`. Cero datos tocados.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0002_google_sub_unique"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="google_sub",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="usuario",
            name="avatar_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]
