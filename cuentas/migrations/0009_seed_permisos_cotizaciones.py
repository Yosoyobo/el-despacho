"""S2b.cotizaciones-v1: seedea PermisoUsuario para Las Cotizaciones en usuarios
existentes. Idempotente vía bulk_create(ignore_conflicts=True).

Defaults: super_admin/dueno = todos (ver, crear, editar, enviar, aprobar,
rechazar, anular); contador = (ver, crear, editar, enviar) sin cerrar ciclo;
diseñador = ninguno.
"""

from __future__ import annotations

from django.db import migrations

DEFAULTS = {
    "super_admin": ["ver", "crear", "editar", "enviar", "aprobar", "rechazar", "anular"],
    "dueno": ["ver", "crear", "editar", "enviar", "aprobar", "rechazar", "anular"],
    "contador": ["ver", "crear", "editar", "enviar"],
}


def seed(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    filas = []
    for u in Usuario.objects.all().order_by("pk"):
        permisos = DEFAULTS.get(u.rol, [])
        for permiso in permisos:
            filas.append(PermisoUsuario(
                usuario=u, modulo="cotizaciones", permiso=permiso, activo=True,
            ))
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="cotizaciones").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0008_seed_permisos_catalogo")]
    operations = [migrations.RunPython(seed, reverse)]
