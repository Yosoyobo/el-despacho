"""S-LC-Feedback-V5 c5: seedea PermisoUsuario para acceso a La Gerencia.

Defaults: super_admin y dueno reciben (gerencia, acceder). Otros roles no.
Heredable: el super_admin puede toglear este permiso a cualquier usuario
desde el directorio. Si lo tiene, puede entrar a `gerencia.ninomeando.com`
con la misma cuenta y verá el atajo "Ajustes" en el sidebar de El Taller.

Idempotente vía bulk_create(ignore_conflicts=True).
"""

from __future__ import annotations

from django.db import migrations

DEFAULTS = {
    "super_admin": ["acceder"],
    "dueno": ["acceder"],
}


def seed(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    filas = []
    for u in Usuario.objects.all().order_by("pk"):
        permisos = DEFAULTS.get(u.rol, [])
        for permiso in permisos:
            filas.append(PermisoUsuario(
                usuario=u, modulo="gerencia", permiso=permiso, activo=True,
            ))
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="gerencia").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0011_seed_permisos_facturacion")]
    operations = [migrations.RunPython(seed, reverse)]
