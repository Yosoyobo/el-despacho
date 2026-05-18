"""Pre-S2b.1: seedea PermisoUsuario para los usuarios existentes con defaults
por rol. Idempotente — re-correr no duplica (bulk_create con ignore_conflicts).
"""

from __future__ import annotations

from django.db import migrations


def seed(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    # Import in-function para que la migración pueda correr sin que lib.* esté
    # disponible al cargar el módulo (defensivo en CI con apps mock).
    from lib.permisos_defaults import DEFAULTS_POR_ROL

    filas = []
    for u in Usuario.objects.all().order_by("pk"):
        para_rol = DEFAULTS_POR_ROL.get(u.rol, {})
        for modulo, permisos in para_rol.items():
            for permiso in permisos:
                filas.append(PermisoUsuario(
                    usuario=u, modulo=modulo, permiso=permiso, activo=True,
                ))
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse_seed(apps, schema_editor):
    pass  # no borramos — los toggles del super_admin tendrían que rehacerse.


class Migration(migrations.Migration):

    dependencies = [("cuentas", "0006_permiso_usuario")]

    operations = [
        migrations.RunPython(seed, reverse_seed),
    ]
