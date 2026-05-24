"""Renombra el label visible del rol `dueno` de 'Dueño' a 'Admin'.

El slug interno se conserva (`dueno`) para no romper checks
`if user.rol == 'dueno'` regados en el código. Sólo cambia lo visible:
descripción del Rol sistema y choices del campo Usuario.rol.
"""

from __future__ import annotations

from django.db import migrations


def actualizar_descripcion_rol_admin(apps, schema_editor):
    Rol = apps.get_model("cuentas", "Rol")
    Rol.objects.filter(nombre="dueno").update(
        descripcion="Admin del despacho. Acceso a todo excepto configuración técnica crítica (solo super_admin).",
    )


def reverse(apps, schema_editor):
    Rol = apps.get_model("cuentas", "Rol")
    Rol.objects.filter(nombre="dueno").update(
        descripcion="Dueño del despacho. Acceso a todo excepto config técnica crítica.",
    )


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0014_rol_y_roles_extra")]
    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="rol",
            field=__import__("django.db.models", fromlist=["CharField"]).CharField(
                choices=[
                    ("super_admin", "Super Admin"),
                    ("dueno", "Admin"),
                    ("contador", "Contador"),
                    ("disenador", "Diseñador"),
                ],
                db_index=True, default="disenador", max_length=20,
            ),
        ),
        migrations.RunPython(actualizar_descripcion_rol_admin, reverse),
    ]
