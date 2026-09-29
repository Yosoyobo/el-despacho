"""Permiso (equipo, ver_historial) — ver el historial de actividad de otros (2026-09-29).

Decisión de Oscar: la presencia de AHORA la ve todo el equipo, pero la línea de
tiempo de un año es más sensible, así que nace **sólo para super_admin y dueño**
y se delega por persona desde /directorio/<id>/permisos/ (§4 #20). El propio
historial lo ve cada quien sin permiso.

El rol se lee aquí sólo para SEMBRAR «como se decidió», no para gatear nada.

Dos caminos, como en la 0046:
· la fila individual de cada usuario — lo que lee `puede()`;
· el JSON de los roles del sistema super_admin y dueño — lo que lee «ver como rol».
Los usuarios NUEVOS lo reciben por `defaults_de()`.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion`. Sólo datos, sin esquema (Bug I). Idempotente.
"""

from __future__ import annotations

from django.db import migrations

MODULO = "equipo"
PERMISO = "ver_historial"
ROLES = ("super_admin", "dueno")


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    filas = [
        PermisoUsuario(usuario_id=pk, modulo=MODULO, permiso=PERMISO, activo=True)
        for pk in Usuario.objects.filter(rol__in=ROLES).order_by("pk").values_list("pk", flat=True)
    ]
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)

    for rol in Rol.objects.filter(clave__in=ROLES):
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
        acciones = set(mapa.get(MODULO) or [])
        if PERMISO in acciones:
            acciones.discard(PERMISO)
            mapa[MODULO] = sorted(acciones)
            rol.permisos = mapa
            rol.save(update_fields=["permisos"])


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0052_registro_actividad")]
    operations = [migrations.RunPython(sembrar, quitar)]
