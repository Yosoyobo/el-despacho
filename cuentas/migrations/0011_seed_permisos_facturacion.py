"""S2b.facturacion-v1: seedea PermisoUsuario para La Facturación en usuarios
existentes. Idempotente vía bulk_create(ignore_conflicts=True).

Defaults: super_admin/dueno/contador = todas (ver, crear, editar, emitir,
cobrar, cancelar); diseñador = ninguna.
"""

from __future__ import annotations

from django.db import migrations

DEFAULTS = {
    "super_admin": ["ver", "crear", "editar", "emitir", "cobrar", "cancelar"],
    "dueno": ["ver", "crear", "editar", "emitir", "cobrar", "cancelar"],
    "contador": ["ver", "crear", "editar", "emitir", "cobrar", "cancelar"],
}


def seed(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    filas = []
    for u in Usuario.objects.all().order_by("pk"):
        permisos = DEFAULTS.get(u.rol, [])
        for permiso in permisos:
            filas.append(PermisoUsuario(
                usuario=u, modulo="facturacion", permiso=permiso, activo=True,
            ))
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="facturacion").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0010_seed_permisos_contaduria_v1")]
    operations = [migrations.RunPython(seed, reverse)]
