"""S-LC-Feedback-V11 — icono por carpeta del sidebar (por usuario).

El orden de las carpetas se deriva del orden de sus items; aquí solo se
persiste el icono elegido para cada carpeta.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0029_seed_permisos_areas_admin"),
    ]

    operations = [
        migrations.CreateModel(
            name="SidebarCarpetaUsuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=40)),
                ("icono", models.CharField(default="folder", max_length=24)),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sidebar_carpetas", to="cuentas.usuario")),
            ],
            options={
                "db_table": "cuentas_sidebar_carpeta_usuario",
                "ordering": ["nombre"],
            },
        ),
        migrations.AddConstraint(
            model_name="sidebarcarpetausuario",
            constraint=models.UniqueConstraint(fields=("usuario", "nombre"), name="sidebar_carpeta_usuario_unico"),
        ),
    ]
