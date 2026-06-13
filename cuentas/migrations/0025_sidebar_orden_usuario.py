"""S-LC-Feedback-V7 — orden del sidebar por usuario (pisa el global)."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0024_rol_miembro_dueno_legacy"),
    ]

    operations = [
        migrations.CreateModel(
            name="SidebarOrdenUsuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.CharField(db_index=True, max_length=40)),
                ("orden", models.PositiveIntegerField(default=100)),
                ("oculto", models.BooleanField(default=False)),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sidebar_orden", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "cuentas_sidebar_orden_usuario",
                "ordering": ["orden", "slug"],
            },
        ),
        migrations.AddConstraint(
            model_name="sidebarordenusuario",
            constraint=models.UniqueConstraint(fields=["usuario", "slug"], name="sidebar_orden_usuario_unico"),
        ),
    ]
