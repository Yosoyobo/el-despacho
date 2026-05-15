"""Hotfix SSO: avatar_url URLField(500) → TextField.

Segundo intento del hotfix (0003 subió de 200 a 500; sigue corto). URLs
de fotos de cuentas Google Workspace exceden 500 chars rutinariamente —
incluyen tokens, hashes y query params largos. En Postgres `text` y
`varchar` tienen el mismo storage/performance; el max_length arbitrario
no aporta nada y solo causa crashes.

Política de aquí en adelante: URLs no se benefician de límite arbitrario;
usar TextField. Documentado en el cierre de SSO de BITACORA.md.

Solo AlterField. Cero RunPython. No-destructiva.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0003_google_fields_grow"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="avatar_url",
            field=models.TextField(blank=True, default=""),
        ),
    ]
