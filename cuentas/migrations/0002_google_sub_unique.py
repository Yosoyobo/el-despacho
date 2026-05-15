"""Sprint SSO Google: hace `google_sub` UNIQUE/NULL y agrega google_email + google_vinculado_en.

Pasos:
1. AlterField: `google_sub` pasa de `default="" / max_length=64` a `null=True / blank=True / max_length=50`.
2. RunPython: convierte filas existentes con `google_sub=""` a `google_sub=NULL` (para que UNIQUE
   no choque cuando agregamos el constraint — sin NULL, dos filas con "" colisionarían).
3. AlterField: agrega `unique=True` al campo.
4. AddField: `google_email`, `google_vinculado_en`.

Reverse (downgrade): NULL → "" antes de remover UNIQUE.
"""

from django.db import migrations, models


def _vacios_a_null(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Usuario.objects.filter(google_sub="").update(google_sub=None)


def _null_a_vacios(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Usuario.objects.filter(google_sub__isnull=True).update(google_sub="")


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="google_sub",
            field=models.CharField(blank=True, db_index=True, max_length=50, null=True),
        ),
        migrations.RunPython(_vacios_a_null, _null_a_vacios),
        migrations.AlterField(
            model_name="usuario",
            name="google_sub",
            field=models.CharField(blank=True, db_index=True, max_length=50, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="usuario",
            name="google_email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name="usuario",
            name="google_vinculado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
