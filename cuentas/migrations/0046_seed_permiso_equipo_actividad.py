"""Permiso (equipo, ver_actividad) — ver quién está en línea (2026-09-28).

Decisión de Oscar: «quién ve: todos». Así que, a diferencia de casi todos los
seeds del repo (sólo super_admin), éste lo concede a TODOS los usuarios y a
TODOS los roles. Sigue siendo granular (§4 #20): el super_admin lo revoca por
usuario desde /directorio/<id>/permisos/, y la fila con `activo=False` gana
sobre cualquier rol.

Dos caminos, a propósito:
· la fila individual a cada usuario existente — es lo que lee `puede()`;
· el JSON de cada Rol — lo que lee «ver como rol», que evalúa SÓLO el rol
  simulado. Sin esto, el super_admin simulando un rol vería la pantalla distinta
  de como la ve de verdad alguien con ese rol.
Los usuarios NUEVOS lo reciben por el signal `auto_seedear_permisos`, que pasa
por `defaults_de()` (y ahí vive `PERMISOS_UNIVERSALES`).

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion` (pasó el 2026-08-22 y tumbó el arranque en producción, porque aquí la
suite corre sobre una base sin usuarios y el bucle no itera).

Idempotente: `ignore_conflicts` en las filas y `set` en el JSON.
"""

from __future__ import annotations

from django.db import migrations

MODULO = "equipo"
PERMISO = "ver_actividad"


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    filas = [
        PermisoUsuario(usuario=u, modulo=MODULO, permiso=PERMISO, activo=True)
        for u in Usuario.objects.all().order_by("pk")
    ]
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)

    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        acciones = set(mapa.get(MODULO) or [])
        if PERMISO in acciones:
            continue
        acciones.add(PERMISO)
        mapa[MODULO] = sorted(acciones)
        rol.permisos = mapa
        rol.save(update_fields=["permisos"])


def quitar(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo=MODULO, permiso=PERMISO).delete()
    Rol = apps.get_model("cuentas", "Rol")
    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        if MODULO in mapa:
            mapa.pop(MODULO)
            rol.permisos = mapa
            rol.save(update_fields=["permisos"])


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0045_usuario_actividad")]
    operations = [migrations.RunPython(sembrar, quitar)]
