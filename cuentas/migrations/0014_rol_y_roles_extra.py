"""S-LC-Feedback-V5 c7: tabla Rol + M2M Usuario.roles_extra + seed de 4
roles sistema (super_admin, dueno, contador, disenador) usando
`DEFAULTS_POR_ROL` de `lib/permisos_defaults.py`.
"""

from __future__ import annotations

from django.db import migrations, models


def seed(apps, schema_editor):
    from lib.permisos_defaults import DEFAULTS_POR_ROL
    Rol = apps.get_model("cuentas", "Rol")
    DESCRIPCIONES = {
        "super_admin": "Acceso total. No se puede editar ni borrar.",
        "dueno": "Dueño del despacho. Acceso a todo excepto config técnica crítica.",
        "contador": "Operación financiera y proyectos en lectura.",
        "disenador": "Solo proyectos asignados + tareas + recados.",
    }
    for nombre, permisos in DEFAULTS_POR_ROL.items():
        Rol.objects.update_or_create(
            nombre=nombre,
            defaults={
                "descripcion": DESCRIPCIONES.get(nombre, ""),
                "permisos": dict(permisos),
                "sistema": True,
            },
        )


def reverse(apps, schema_editor):
    apps.get_model("cuentas", "Rol").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0013_sidebar_orden")]
    operations = [
        migrations.CreateModel(
            name="Rol",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(db_index=True, max_length=60, unique=True)),
                ("descripcion", models.CharField(blank=True, default="", max_length=200)),
                ("permisos", models.JSONField(blank=True, default=dict)),
                ("sistema", models.BooleanField(default=False)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "cuentas_rol", "ordering": ["nombre"]},
        ),
        migrations.AddField(
            model_name="usuario",
            name="roles_extra",
            field=models.ManyToManyField(blank=True, related_name="usuarios", to="cuentas.rol"),
        ),
        migrations.RunPython(seed, reverse),
    ]
