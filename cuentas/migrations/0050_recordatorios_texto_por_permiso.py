"""Sólo el texto de ayuda: el aviso «a los admins» ya no va por rol sino a quien
gestiona proyectos (`proyectos.editar`), S-Fin-Sep29. Sin cambio de esquema real."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0049_comentarios_en_roles_del_sistema")]

    operations = [
        migrations.AlterField(
            model_name="configrecordatorios",
            name="incluir_admins",
            field=models.BooleanField(
                default=False,
                help_text="Notificar también a quien gestiona proyectos (permiso proyectos.editar).",
            ),
        ),
    ]
