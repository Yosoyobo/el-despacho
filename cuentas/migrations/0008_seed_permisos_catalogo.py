"""Pre-S2b.2: seedea los 7 permisos nuevos de `catalogo` para los usuarios
existentes según defaults por rol. Idempotente (bulk_create ignore_conflicts).
"""

from __future__ import annotations

from django.db import migrations


def seed_catalogo(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    from lib.permisos_defaults import DEFAULTS_POR_ROL

    filas = []
    for u in Usuario.objects.all().order_by("pk"):
        permisos_catalogo = DEFAULTS_POR_ROL.get(u.rol, {}).get("catalogo", [])
        for permiso in permisos_catalogo:
            filas.append(PermisoUsuario(
                usuario=u, modulo="catalogo", permiso=permiso, activo=True,
            ))
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse_seed(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="catalogo").delete()


class Migration(migrations.Migration):

    dependencies = [("cuentas", "0007_seed_permisos_defaults")]

    operations = [
        migrations.RunPython(seed_catalogo, reverse_seed),
    ]
