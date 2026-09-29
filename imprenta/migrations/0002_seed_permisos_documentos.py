"""Las llaves de La Imprenta — sólo datos (Bug I: el esquema quedó en 0001).

«Como hoy» (regla §4 #20): la pantalla de Documentos vivía en Ajustes y se
abría con `ajustes.acceder`. El módulo nuevo `documentos` nace para las MISMAS
personas, con todas sus acciones:

  · super_admin (efectivo)                  → todas
  · quien HOY tiene `ajustes.acceder`
    efectivo (fila encendida o rol asignado) → todas
  · nadie más.

Dos pasos (el patrón de `checador/0010`):

  1. JSON del rol del sistema `super_admin`, igual que `DEFAULTS_POR_ROL`, y de
     todo rol que ya traiga `ajustes.acceder`: para quien lo reciba mañana y para
     «ver como rol».
  2. Una fila por persona que califica. Una fila de `documentos` que ya exista
     no se pisa.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion` (`cuentas/0044` tumbó un arranque en producción por eso).
"""

from django.db import migrations

MODULO = "documentos"
TODO = ("ver", "editar_estilo", "editar_notas", "editar_datos")


def _tiene_ajustes(Permiso, usuario) -> bool:
    fila = Permiso.objects.filter(usuario=usuario, modulo="ajustes", permiso="acceder").first()
    if fila is not None:
        return bool(fila.activo)
    return any("acceder" in ((r.permisos or {}).get("ajustes") or [])
               for r in usuario.roles_extra.all())


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        if rol.clave != "super_admin" and "acceder" not in (mapa.get("ajustes") or []):
            continue
        actuales = set(mapa.get(MODULO) or [])
        if set(TODO) <= actuales:
            continue
        mapa[MODULO] = sorted(actuales | set(TODO))
        rol.permisos = mapa
        rol.save(update_fields=["permisos"])

    for usuario in Usuario.objects.all():
        roles = {usuario.rol} if usuario.rol else set()
        roles.update(usuario.roles_extra.values_list("clave", flat=True))
        if "super_admin" not in roles and not _tiene_ajustes(Permiso, usuario):
            continue
        for accion in TODO:
            Permiso.objects.get_or_create(
                usuario=usuario, modulo=MODULO, permiso=accion, defaults={"activo": True},
            )


def quitar(apps, schema_editor):
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")
    Permiso.objects.filter(modulo=MODULO).delete()
    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        if MODULO in mapa:
            mapa.pop(MODULO)
            rol.permisos = mapa
            rol.save(update_fields=["permisos"])


class Migration(migrations.Migration):

    dependencies = [
        ("imprenta", "0001_initial"),
        ("cuentas", "0051_seed_permiso_contaduria_cargar"),
    ]

    operations = [migrations.RunPython(sembrar, quitar)]
