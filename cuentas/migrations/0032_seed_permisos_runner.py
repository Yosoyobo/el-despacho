"""S-LC-Proyecto-V2 (Oscar): seedea el permiso (runner, recibir) — elegibilidad
para recibir entregas/recolecciones como repartidor.

Default activo para TODOS los usuarios existentes (todos pueden ser runner).
El super_admin revoca a quien no deba serlo desde /directorio/<id>/permisos/.
El signal `auto_seedear_permisos` cubre usuarios nuevos (default en los 4 roles).

Idempotente vía bulk_create(ignore_conflicts=True).
"""

from __future__ import annotations

from django.db import migrations


def seed(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    filas = [
        PermisoUsuario(usuario=u, modulo="runner", permiso="recibir", activo=True)
        for u in Usuario.objects.all().order_by("pk")
    ]
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="runner").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0031_usuario_formato_hora")]
    operations = [migrations.RunPython(seed, reverse)]
