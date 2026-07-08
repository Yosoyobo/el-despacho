"""Soft-archive de proyectos (LC 2026-07).

Permite ocultar proyectos de prueba/duplicados sin borrarlos, distinto del
estado «Cancelado». El borrado permanente (super_admin, solo proyectos sin
movimientos financieros) no requiere schema — usa .delete().
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0020_proyecto_proveedor_iva"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="proyecto",
            name="archivado",
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="archivado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="archivado_por",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="proyectos_archivados",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
