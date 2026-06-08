"""S-Estados-Color-HEX: seedea PermisoUsuario para el chat de El Chalán.

El chat (`/chalan/`) deja de ser visible para todos por defecto y pasa a
gatearse por el permiso granular (chalan, usar). Para PRESERVAR el
comportamiento actual, todos los usuarios existentes (sin importar rol)
reciben el permiso activo. El super_admin lo revoca por usuario/rol desde
/directorio/<id>/permisos/.

Idempotente vía bulk_create(ignore_conflicts=True).
"""

from __future__ import annotations

from django.db import migrations


def seed(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    filas = [
        PermisoUsuario(usuario=u, modulo="chalan", permiso="usar", activo=True)
        for u in Usuario.objects.all().order_by("pk")
    ]
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="chalan").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0015_rename_dueno_admin_labels")]
    operations = [migrations.RunPython(seed, reverse)]
