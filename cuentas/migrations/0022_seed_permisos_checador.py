"""S-Checador: seedea PermisoUsuario del módulo `checador` por rol.

`checar` es para todo el staff (los 4 roles). Las funciones de supervisión
(ver_equipo, aprobar_correcciones, configurar_horarios, exportar) van a
super_admin y dueno; el contador recibe ver_equipo + exportar (insumo para
nómina/costos). El signal `auto_seedear_permisos` cubre usuarios nuevos.

Idempotente vía bulk_create(ignore_conflicts=True).
"""

from __future__ import annotations

from django.db import migrations

PERMISOS_POR_ROL = {
    "super_admin": ["checar", "ver_equipo", "aprobar_correcciones", "configurar_horarios", "exportar"],
    "dueno": ["checar", "ver_equipo", "aprobar_correcciones", "configurar_horarios", "exportar"],
    "contador": ["checar", "ver_equipo", "exportar"],
    "disenador": ["checar"],
}


def seed(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    filas = []
    for u in Usuario.objects.all().order_by("pk"):
        for permiso in PERMISOS_POR_ROL.get(u.rol, ["checar"]):
            filas.append(PermisoUsuario(usuario=u, modulo="checador", permiso=permiso, activo=True))
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="checador").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0021_usuario_ficha_directorio")]
    operations = [migrations.RunPython(seed, reverse)]
