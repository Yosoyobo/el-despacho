"""Las entradas y salidas del equipo son de quien dirige (2026-10-05).

Decisión de Oscar: «sólo los directores pueden ver esa actividad». Desde ahora
`checador.ver_equipo` también abre las horas de todo el equipo
(`lib.permisos.puede_ver_horas_trabajadas_de`), así que deja de ser del contador:
de arranque lo traen super_admin y dueño, y se delega por persona desde
/directorio/<id>/permisos/ (§4 #20). El contador conserva `exportar` (el CSV de
jornadas para la nómina).

El rol se lee aquí sólo para SEMBRAR «como se decidió», no para gatear nada.

Dos caminos, como en la 0053:
· la fila individual de cada usuario — lo que lee `puede()`;
· el JSON de los roles del sistema — lo que lee «ver como rol».
Los usuarios NUEVOS lo reciben por `defaults_de()`.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion`. Sólo datos, sin esquema (Bug I). Idempotente.
"""

from __future__ import annotations

from django.db import migrations

MODULO = "checador"
PERMISO = "ver_equipo"
DIRECTORES = ("super_admin", "dueno")
PIERDE = "contador"


def _rol_json(Rol, clave: str, *, poner: bool) -> None:
    for rol in Rol.objects.filter(clave=clave):
        mapa = dict(rol.permisos or {})
        acciones = set(mapa.get(MODULO) or [])
        if (PERMISO in acciones) == poner:
            continue
        if poner:
            acciones.add(PERMISO)
        else:
            acciones.discard(PERMISO)
        mapa[MODULO] = sorted(acciones)
        rol.permisos = mapa
        rol.save(update_fields=["permisos"])


def aplicar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    filas = [
        PermisoUsuario(usuario_id=pk, modulo=MODULO, permiso=PERMISO, activo=True)
        for pk in Usuario.objects.filter(rol__in=DIRECTORES).order_by("pk").values_list("pk", flat=True)
    ]
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)
    PermisoUsuario.objects.filter(
        usuario__rol=PIERDE, modulo=MODULO, permiso=PERMISO,
    ).delete()

    for clave in DIRECTORES:
        _rol_json(Rol, clave, poner=True)
    _rol_json(Rol, PIERDE, poner=False)


def revertir(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")
    filas = [
        PermisoUsuario(usuario_id=pk, modulo=MODULO, permiso=PERMISO, activo=True)
        for pk in Usuario.objects.filter(rol=PIERDE).order_by("pk").values_list("pk", flat=True)
    ]
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)
    _rol_json(Rol, PIERDE, poner=True)


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0055_checador_por_actividad")]
    operations = [migrations.RunPython(aplicar, revertir)]
